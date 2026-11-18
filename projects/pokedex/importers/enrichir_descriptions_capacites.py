#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Complète UNIQUEMENT les descriptions manquantes de CAPACITE depuis PokéAPI.

Usage Windows :
    py -m pip install requests "psycopg[binary]"
    py .\enrichir_descriptions_capacites.py --dry-run
    py .\enrichir_descriptions_capacites.py

Ne supprime rien, ne remplace aucune description existante, ne modifie pas
les Pokémon ni le Pokédex personnel. Les IDs de CAPACITE sont ceux de PokéAPI
comme dans les importeurs précédents.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import psycopg
except ImportError:
    sys.exit('Installer : py -m pip install "psycopg[binary]"')

API_ROOT = 'https://pokeapi.co/api/v2'
DB_NAME = 'pokedex_dev'
CACHE = Path(__file__).resolve().parent / '.pokeapi_cache'


def nettoyer(texte: object) -> str | None:
    if not isinstance(texte, str) or not texte.strip():
        return None
    # Préserver les libellés humains des liens documentaires PokéAPI.
    texte = re.sub(r'\[([^\]]+)\]\{[^}]+\}', r'\1', texte)
    texte = re.sub(r'\s+', ' ', texte.replace('\u00ad', ' ')).strip()
    return texte[:500] if texte else None


def prendre(entrees: object, champ: str, langue: str) -> str | None:
    if not isinstance(entrees, list):
        return None
    for entree in reversed(entrees):
        if not isinstance(entree, dict):
            continue
        if (entree.get('language') or {}).get('name') != langue:
            continue
        texte = nettoyer(entree.get(champ))
        if texte:
            return texte
    return None


def choisir_description(obj: dict) -> tuple[str | None, str | None]:
    # Priorité absolue à la description de jeu en français.
    candidats = [
        ('flavor_text_entries', 'flavor_text', 'fr', 'description FR'),
        ('effect_entries', 'short_effect', 'fr', 'effet court FR'),
        ('effect_entries', 'effect', 'fr', 'effet FR'),
        ('flavor_text_entries', 'flavor_text', 'en', 'description EN'),
        ('effect_entries', 'short_effect', 'en', 'effet court EN'),
        ('effect_entries', 'effect', 'en', 'effet EN'),
    ]
    for tableau, champ, langue, source in candidats:
        texte = prendre(obj.get(tableau), champ, langue)
        if not texte:
            continue
        if '$effect_chance' in texte:
            chance = obj.get('effect_chance')
            if not isinstance(chance, (int, float)):
                continue
            texte = texte.replace('$effect_chance', str(chance))
        # Éviter de stocker des placeholders techniques non résolus.
        if re.search(r'\$[A-Za-z_]+', texte):
            continue
        return texte, source
    return None, None


class API:
    def __init__(self, refresh: bool = False):
        CACHE.mkdir(exist_ok=True, parents=True)
        self.refresh = refresh
        self.session = requests.Session()
        retries = Retry(total=4, backoff_factor=0.8,
                        status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.headers['User-Agent'] = 'Toms-Pokedex-Enrichissement/1.0'

    def move(self, move_id: int) -> dict:
        url = f'{API_ROOT}/move/{move_id}/'
        cache = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.json')
        if cache.is_file() and not self.refresh:
            try:
                obj = json.loads(cache.read_text(encoding='utf-8'))
                if isinstance(obj, dict) and obj.get('id') == move_id:
                    return obj
            except (ValueError, OSError):
                pass
        response = self.session.get(url, timeout=(12, 35))
        response.raise_for_status()
        obj = response.json()
        if not isinstance(obj, dict) or obj.get('id') != move_id:
            raise ValueError(f'Réponse inattendue pour la capacité #{move_id}')
        tmp = cache.with_suffix('.tmp')
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        tmp.replace(cache)
        return obj


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Prévisualiser sans écriture')
    parser.add_argument('--refresh-cache', action='store_true', help='Actualiser les réponses PokéAPI')
    args = parser.parse_args()

    password = os.environ.get('PGPASSWORD') or getpass.getpass('Mot de passe PostgreSQL : ')
    conn = psycopg.connect(
        dbname=DB_NAME,
        host=os.environ.get('PGHOST', 'localhost'),
        port=os.environ.get('PGPORT', '5432'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=password,
        connect_timeout=12,
    )

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT current_database()')
            if cur.fetchone()[0] != DB_NAME:
                raise RuntimeError('Base incorrecte, aucune modification.')
            cur.execute('''
                SELECT id_capacite, nom_capacite
                FROM public.capacite
                WHERE description_capacite IS NULL
                   OR BTRIM(description_capacite) = ''
                ORDER BY id_capacite
            ''')
            manquantes = cur.fetchall()
        print(f'Capacités sans description : {len(manquantes)}')
        api = API(args.refresh_cache)
        a_completer = []
        sans_source = []
        erreurs = []

        # Toutes les requêtes API précèdent les écritures PostgreSQL.
        for move_id, nom in manquantes:
            try:
                obj = api.move(move_id)
                texte, origine = choisir_description(obj)
                if texte:
                    a_completer.append((texte, move_id, origine, nom))
                    print(f'[SOURCE] #{move_id} {nom} : {origine}')
                else:
                    sans_source.append((move_id, nom))
                    print(f'[NON DISPONIBLE] #{move_id} {nom}')
            except Exception as exc:
                erreurs.append((move_id, nom, str(exc)))
                print(f'[ERREUR] #{move_id} {nom} : {exc}', file=sys.stderr)

        if erreurs:
            print(f'{len(erreurs)} erreur(s) PokéAPI : aucune écriture effectuée.')
            raise SystemExit(2)

        mises_a_jour = 0
        if not args.dry_run and a_completer:
            with conn.cursor() as cur:
                for description, move_id, _origine, _nom in a_completer:
                    cur.execute('''
                        UPDATE public.capacite
                        SET description_capacite = %s
                        WHERE id_capacite = %s
                          AND (description_capacite IS NULL
                               OR BTRIM(description_capacite) = '')
                    ''', (description, move_id))
                    mises_a_jour += cur.rowcount
            conn.commit()
        else:
            conn.rollback()

        print('\n===== BILAN ENRICHISSEMENT CAPACITES =====')
        print(f'Sans description au départ : {len(manquantes)}')
        print(f'Textes trouvés dans PokéAPI : {len(a_completer)}')
        print(f'Absents de PokéAPI : {len(sans_source)}')
        print(f'Descriptions effectivement ajoutées : {mises_a_jour}')
        print('Mode : prévisualisation' if args.dry_run else 'Mode : import réel')
        print('Aucune description existante ni autre table modifiée.')
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
