#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrichissement factuel des descriptions de ZONE du Pokédex (PokéAPI v2).

Pour chaque zone sans description :
  - vérifie la fiche /location/{id}/ de PokéAPI ;
  - récupère le nombre de sous-zones et jusqu'à deux noms FR/EN attestés ;
  - ajoute le nombre de Pokémon localisés dans cette zone, et trois exemples,
    d'après SE_TROUVER dans la base EXISTANTE (données multi-éditions).

IMPORTANT : ces textes sont des SYNTHESES de données, pas des descriptions
narratives officielles de PokéAPI. Les zones dépourvues de données spécifiques
(sans sous-zone, sans rencontre) restent vides : aucune information inventée.

Garanti : ne modifie que public.zone.description_zone si NULL / vide.
Ne change ni les relations, ni les Pokémon, ni les dresseurs, ni le schéma.
Reutilise le cache .pokeapi_cache créé par les importeurs précédents.

Windows :
  py -m pip install requests "psycopg[binary]"
  py .\\enrichir_descriptions_zones.py --dry-run
  py .\\enrichir_descriptions_zones.py
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import psycopg
except ImportError:
    sys.exit('Dépendance manquante : py -m pip install "psycopg[binary]"')

BASE = 'https://pokeapi.co/api/v2'
DB_NAME = 'pokedex_dev'
CACHE = Path(__file__).resolve().parent / '.pokeapi_cache'
MAX_DESCRIPTION = 500  # Colonne ZONE.description_zone VARCHAR(500)


def nettoyer(texte: str | None, maxi: int = 100) -> str | None:
    if not isinstance(texte, str):
        return None
    resultat = re.sub(r'\s+', ' ', texte.replace('\u00ad', ' ')).strip()
    return resultat[:maxi] or None


def nom_localise(obj: dict) -> str | None:
    """Nom réel fourni par l'API; ne traduit pas les slugs artificiellement."""
    entrees = obj.get('names') or []
    for langue in ('fr', 'en'):
        for entree in entrees:
            if (entree.get('language') or {}).get('name') == langue:
                nom = nettoyer(entree.get('name'), 90)
                if nom:
                    return nom
    return None


def url_pokeapi(url: str) -> bool:
    cible = urlparse(url)
    return (cible.scheme == 'https' and cible.netloc == 'pokeapi.co'
            and cible.path.startswith('/api/v2/') and not cible.query
            and not cible.fragment)


class PokeAPI:
    def __init__(self, actualiser: bool = False) -> None:
        CACHE.mkdir(exist_ok=True, parents=True)
        self.actualiser = actualiser
        self.session = requests.Session()
        retry = Retry(total=3, connect=3, read=3, backoff_factor=.8,
                      status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.headers['User-Agent'] = 'Toms-Pokedex-Zones/1.0 (personal-project)'
        self.reseau = 0
        self.cache = 0

    def get(self, endpoint_ou_url: str) -> dict:
        url = (endpoint_ou_url if endpoint_ou_url.startswith('https://')
               else f'{BASE}/{endpoint_ou_url.lstrip("/")}')
        if not url_pokeapi(url):
            raise ValueError(f'URL non autorisée : {url}')
        chemin = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.json')
        if chemin.exists() and not self.actualiser:
            try:
                donnees = json.loads(chemin.read_text(encoding='utf-8'))
                if isinstance(donnees, dict):
                    self.cache += 1
                    return donnees
            except (ValueError, OSError):
                pass
        reponse = self.session.get(url, timeout=(12, 40))
        reponse.raise_for_status()
        donnees = reponse.json()
        if not isinstance(donnees, dict):
            raise ValueError(f'Objet JSON inattendu : {url}')
        temporaire = chemin.with_suffix('.tmp')
        temporaire.write_text(json.dumps(donnees, ensure_ascii=False), encoding='utf-8')
        temporaire.replace(chemin)
        self.reseau += 1
        time.sleep(.07)
        return donnees


def compact(texte: str, limite: int = MAX_DESCRIPTION) -> str:
    if len(texte) <= limite:
        return texte
    coupee = texte[:limite - 1].rsplit(' ', 1)[0].rstrip(' ,;:')
    return coupee + '…'


def construire_description(region: str, nombre_aires: int,
                            aires_nommees: list[str], nombre_pokemon: int,
                            exemples: list[str]) -> str | None:
    """Pas de remplissage factice si seules région et dénomination sont connues."""
    if nombre_aires <= 0 and nombre_pokemon <= 0:
        return None
    phrases = [f'Lieu de la région {region}.']
    if nombre_aires > 0:
        if nombre_aires == 1:
            passage = 'PokéAPI répertorie 1 sous-zone'
        else:
            passage = f'PokéAPI répertorie {nombre_aires} sous-zones'
        if aires_nommees:
            passage += ' (notamment ' + ', '.join(aires_nommees[:2]) + ')'
        phrases.append(passage + '.')
    if nombre_pokemon > 0:
        mot = 'espèce' if nombre_pokemon == 1 else 'espèces'
        passage = f'{nombre_pokemon} {mot} associées à ce lieu dans la base (rencontres multi-éditions)'
        if exemples:
            passage += ', dont ' + ', '.join(exemples[:3])
        phrases.append(passage + '.')
    return compact(' '.join(phrases))


def charger_zones(conn) -> list[tuple]:
    # Un seul SELECT : la base constitue la source de vérité des associations.
    with conn.cursor() as cur:
        cur.execute('''
            SELECT z.id_zone, z.nom_zone, r.nom_region, z.id_region,
                   COUNT(st.id_pokemon)::integer AS n_pokemon,
                   COALESCE(
                     (ARRAY_AGG(p.nom_pokemon ORDER BY p.id_pokemon)
                      FILTER (WHERE p.id_pokemon IS NOT NULL))[1:3],
                     ARRAY[]::varchar[]
                   ) AS exemples
            FROM public.zone AS z
            JOIN public.region AS r ON r.id_region = z.id_region
            LEFT JOIN public.se_trouver AS st ON st.id_zone = z.id_zone
            LEFT JOIN public.pokemon AS p ON p.id_pokemon = st.id_pokemon
            WHERE z.description_zone IS NULL OR BTRIM(z.description_zone) = ''
            GROUP BY z.id_zone, z.nom_zone, r.nom_region, z.id_region
            ORDER BY z.id_zone
        ''')
        return cur.fetchall()


def preparer(api: PokeAPI, zones: list[tuple], max_aires: int):
    ajouts = []
    sans_detail = []
    erreurs = []
    for idx, (id_zone, nom_zone, region, id_region, n_pokemon, exemples) in enumerate(zones, 1):
        try:
            loc = api.get(f'location/{id_zone}/')
            if loc.get('id') != id_zone:
                raise ValueError('identifiant de lieu incohérent')
            lien_region = (loc.get('region') or {}).get('url') or ''
            if lien_region:
                match = re.search(r'/region/(\d+)/?$', lien_region)
                if not match or int(match.group(1)) != id_region:
                    raise ValueError(f'la région PokéAPI ne correspond pas à {region}')
            refs_aires = loc.get('areas') or []
            noms = []
            for ref in refs_aires[:max_aires]:
                area = api.get(ref['url'])
                # Protection contre association à un autre lieu
                ref_parent = (area.get('location') or {}).get('url') or ''
                if not ref_parent.endswith(f'/location/{id_zone}/'):
                    raise ValueError(f'sous-zone {ref.get("name")} associée à un autre lieu')
                nom = nom_localise(area)
                if nom and nom not in noms:
                    noms.append(nom)
            description = construire_description(
                region, len(refs_aires), noms, n_pokemon, list(exemples or []))
            if description:
                ajouts.append((description, id_zone))
            else:
                sans_detail.append((id_zone, nom_zone, region))
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
            erreurs.append((id_zone, nom_zone, str(exc)))
            print(f'  [NON TRAITÉ] #{id_zone} {nom_zone}: {exc}', flush=True)
        if idx % 50 == 0 or idx == len(zones):
            print(f'  {idx}/{len(zones)} lieux | enrichissables : {len(ajouts)} '
                  f'| sans détail : {len(sans_detail)} | erreurs : {len(erreurs)}',
                  flush=True)
    return ajouts, sans_detail, erreurs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Prévisualiser, sans UPDATE')
    parser.add_argument('--refresh-cache', action='store_true', help='Recharger PokéAPI')
    parser.add_argument('--max-aires', type=int, default=2,
                        help='Nombre maximal de sous-zones dont le nom est lu par lieu (défaut : 2)')
    args = parser.parse_args()
    if not 0 <= args.max_aires <= 5:
        parser.error('--max-aires doit être compris entre 0 et 5')

    mot_de_passe = os.getenv('PGPASSWORD') or getpass.getpass('Mot de passe PostgreSQL : ')
    conn = psycopg.connect(
        dbname=DB_NAME, host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'), user=os.getenv('PGUSER', 'postgres'),
        password=mot_de_passe, connect_timeout=12, autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT current_database()')
            if cur.fetchone()[0] != DB_NAME:
                raise RuntimeError('Base PostgreSQL incorrecte : exécution annulée')
            for table in ('zone', 'region', 'se_trouver', 'pokemon'):
                cur.execute('SELECT to_regclass(%s)', (f'public.{table}',))
                if cur.fetchone()[0] is None:
                    raise RuntimeError(f'Table absente : public.{table}')
        zones = charger_zones(conn)
        print(f'Zones sans description : {len(zones)}', flush=True)
        if not zones:
            print('Rien à compléter : aucune écriture.'); return
        api = PokeAPI(args.refresh_cache)
        ajouts, sans_detail, erreurs = preparer(api, zones, args.max_aires)

        print('\nEXEMPLES DE DESCRIPTIONS PROPOSÉES :')
        for description, zid in ajouts[:5]:
            print(f'  Zone #{zid} : {description}')
        print('\n===== BILAN ENRICHISSEMENT ZONES =====')
        print(f'Zones examinées : {len(zones)}')
        print(f'Descriptions factuelles préparées : {len(ajouts)}')
        print(f'Sans information spécifique suffisante : {len(sans_detail)}')
        print(f'Erreurs API / incohérences (non modifiées) : {len(erreurs)}')
        print(f'PokéAPI : {api.cache} réponses du cache ; {api.reseau} téléchargements')
        if args.dry_run:
            print('MODE PRÉVISUALISATION : aucune écriture SQL.')
            return
        if not ajouts:
            print('Aucune description ajoutée.')
            return

        # Une seule transaction : en cas d'échec SQL, aucun ajout n'est conservé.
        modifiees = 0
        with conn.transaction():
            with conn.cursor() as cur:
                for description, zid in ajouts:
                    cur.execute('''
                        UPDATE public.zone
                           SET description_zone = %s
                         WHERE id_zone = %s
                           AND (description_zone IS NULL OR BTRIM(description_zone) = '')
                    ''', (description, zid))
                    modifiees += cur.rowcount
        print(f'Descriptions effectivement ajoutées : {modifiees}')
        print('Autres champs, relations, Pokémon et Pokédex personnels : inchangés.')
        if erreurs:
            print('Les zones en erreur n’ont pas été modifiées ; relancer pour retenter.')
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrompu avant la transaction d’écriture (ou transaction annulée).', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'ERREUR : {exc}', file=sys.stderr)
        sys.exit(1)
