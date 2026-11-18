#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Lot 4 - Géographie de Kanto et habitats des 151 Pokémon (PokéAPI v2).

Alimente : REGION, ZONE, HABITAT, VIVRE_HABITAT, SE_TROUVER.
APPARAITRE_REGION est alimentée par le trigger RG07 lorsque SE_TROUVER est ajouté.
ACCUEILLIR_HABITAT n'est PAS alimentée : l'API n'atteste pas cette relation.

Correspondance : ZONE = location PokéAPI (ville, route, grotte, etc.).
Les location-area servent seulement à identifier les rencontres dans ce lieu.
Les rencontres proviennent par défaut de Rouge Feu et Vert Feuille :
ce ne sont PAS des données historiques Rouge/Bleu.
Le champ frequence_rencontre reste NULL : agréger des chances de rencontre
par méthodes, versions et sous-zones serait trompeur.

Préparation Windows : py -m pip install requests "psycopg[binary]"
Prévisualisation      : py .\import_pokedex_geographie.py --dry-run
Importation           : py .\import_pokedex_geographie.py

N'affecte ni les Pokémon, ni les évolutions, ni les capacités.
L'importation est transactionnelle, incrémentale et relançable.
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
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import psycopg
except ImportError:
    sys.exit('Dépendance manquante : py -m pip install "psycopg[binary]"')

DB_NAME = 'pokedex_dev'
BASE = 'https://pokeapi.co/api/v2'
CACHE_DIR = Path(__file__).resolve().parent / '.pokeapi_cache'
VERSIONS = frozenset(('firered', 'leafgreen'))


def resource_id(resource: dict) -> int:
    match = re.search(r'/([0-9]+)/?$', resource['url'])
    if not match:
        raise ValueError(f'ID PokéAPI absent : {resource}')
    return int(match.group(1))


def clean(value: str | None, max_len: int) -> str | None:
    if not isinstance(value, str):
        return None
    result = re.sub(r'\s+', ' ', value.replace('\u00ad', '')).strip()
    return result[:max_len] or None


def name_fr(obj: dict, max_len: int, fallback: str | None = None) -> str:
    names = obj.get('names') or []
    for lang in ('fr', 'en'):
        for entry in names:
            if entry.get('language', {}).get('name') == lang:
                name = clean(entry.get('name'), max_len)
                if name:
                    return name
    name = clean(fallback or obj.get('name'), max_len)
    if not name:
        raise ValueError(f'Nom absent pour la ressource #{obj.get("id")}.')
    return name


class PokeAPI:
    def __init__(self, refresh: bool = False):
        self.refresh = refresh
        self.session = requests.Session()
        retries = Retry(total=4, connect=4, read=3, backoff_factor=0.9,
                        status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.headers.update({'User-Agent': 'Pokedex-Looping-Geographie/1.0 (educational)'})
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, endpoint_or_url: str) -> dict:
        url = (endpoint_or_url if endpoint_or_url.startswith('https://')
               else f'{BASE}/{endpoint_or_url.lstrip("/")}')
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'pokeapi.co'
                or not parsed.path.startswith('/api/v2/') or parsed.query):
            raise ValueError(f'URL externe refusée : {url}')
        target = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.json')
        if target.exists() and not self.refresh:
            try:
                cached = json.loads(target.read_text(encoding='utf-8'))
                if isinstance(cached, dict):
                    return cached
            except (ValueError, OSError):
                target.unlink(missing_ok=True)
        response = self.session.get(url, timeout=(12, 40))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f'JSON inattendu pour {url}')
        tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        tmp.replace(target)
        time.sleep(.1)
        return payload


@dataclass
class GeographicData:
    region: tuple[int, str]
    zones: dict[int, tuple[str, int]]
    habitats: dict[int, str]
    species_habitats: set[tuple[int, int]]
    locations: set[tuple[int, int]]
    areas_count: int
    matching_entries: int
    pokemon_without_habitat: list[int]


def collect(api: PokeAPI, versions: frozenset[str] = VERSIONS) -> GeographicData:
    """Télécharger toutes les données AVANT la première écriture SQL."""
    region = api.get('region/kanto/')
    region_id = int(region['id'])
    region_label = name_fr(region, 100, 'Kanto')

    zones: dict[int, tuple[str, int]] = {}
    encounter_links: set[tuple[int, int]] = set()
    seen_area_urls: set[str] = set()
    matching_entries = 0
    place_refs = sorted(region.get('locations', []), key=resource_id)
    print(f'Kanto : {len(place_refs)} lieux PokéAPI à parcourir.', flush=True)

    for index, ref in enumerate(place_refs, start=1):
        location = api.get(ref['url'])
        loc_id = int(location['id'])
        loc_region = location.get('region') or {}
        if loc_region.get('name') != 'kanto':
            raise ValueError(f'Lieu #{loc_id} non rattaché à Kanto : {loc_region}')
        label = name_fr(location, 100, ref.get('name'))
        zones[loc_id] = (label, region_id)
        current_links: set[tuple[int, int]] = set()
        for area_ref in location.get('areas', []):
            if area_ref['url'] in seen_area_urls:
                continue
            seen_area_urls.add(area_ref['url'])
            area = api.get(area_ref['url'])
            if resource_id(area['location']) != loc_id:
                raise ValueError(f'Sous-zone #{area.get("id")} incohérente avec lieu #{loc_id}.')
            for entry in area.get('pokemon_encounters', []):
                pid = resource_id(entry['pokemon'])
                if not 1 <= pid <= 151:
                    continue
                valid = any(detail.get('version', {}).get('name') in versions
                            for detail in entry.get('version_details', []))
                if valid:
                    current_links.add((pid, loc_id))
                    matching_entries += 1
        encounter_links.update(current_links)
        if index % 10 == 0 or index == len(place_refs):
            print(f'Lieux : {index}/{len(place_refs)} | sous-zones : {len(seen_area_urls)} '
                  f'| localisations : {len(encounter_links)}', flush=True)

    habitats: dict[int, str] = {}
    species_habitats: set[tuple[int, int]] = set()
    without_habitat: list[int] = []
    for poke_id in range(1, 152):
        species = api.get(f'pokemon-species/{poke_id}/')
        habitat_ref = species.get('habitat')
        if not habitat_ref:
            without_habitat.append(poke_id)
            continue
        habitat_id = resource_id(habitat_ref)
        if habitat_id not in habitats:
            habitat = api.get(habitat_ref['url'])
            habitats[habitat_id] = name_fr(habitat, 100, habitat_ref.get('name'))
        species_habitats.add((poke_id, habitat_id))
    if not zones:
        raise ValueError('PokéAPI ne retourne aucun lieu pour Kanto.')
    return GeographicData((region_id, region_label), zones, habitats,
                          species_habitats, encounter_links,
                          len(seen_area_urls), matching_entries, without_habitat)


def preflight(conn) -> None:
    with conn.cursor() as cur:
        cur.execute('SELECT current_database()')
        if cur.fetchone()[0] != DB_NAME:
            raise RuntimeError('Base inattendue : opération annulée.')
        for table in ('region', 'zone', 'habitat', 'vivre_habitat', 'se_trouver',
                      'apparaitre_region', 'pokemon'):
            cur.execute('SELECT to_regclass(%s)', (f'public.{table}',))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f'Table absente : {table}')
        cur.execute('SELECT COUNT(*) FROM pokemon WHERE id_pokemon BETWEEN 1 AND 151')
        count = cur.fetchone()[0]
        if count != 151:
            raise RuntimeError(f'{count}/151 Pokémon Kanto présents : import interrompu.')
        cur.execute('''
            SELECT COUNT(*)
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = 'se_trouver'
              AND t.tgname = %s AND NOT t.tgisinternal
        ''', ('trg_rg07_se_trouver',))
        if cur.fetchone()[0] != 1:
            raise RuntimeError('Trigger RG07 requis absent : trg_rg07_se_trouver.')


def persist(conn, data: GeographicData) -> tuple[int, int, int, int, int]:
    inserted = [0, 0, 0, 0, 0]
    with conn.transaction():
        with conn.cursor() as cur:
            rid, rname = data.region
            cur.execute('''
                INSERT INTO region (id_region, nom_region)
                VALUES (%s, %s)
                ON CONFLICT (id_region) DO NOTHING
            ''', (rid, rname))
            inserted[0] += cur.rowcount
            cur.execute('SELECT nom_region FROM region WHERE id_region = %s', (rid,))
            if cur.fetchone()[0] != rname:
                raise RuntimeError('Conflit de nom pour la région Kanto : aucune écriture conservée.')

            for zid, (name, region_id) in sorted(data.zones.items()):
                cur.execute('''
                    INSERT INTO zone (id_zone, nom_zone, id_region)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_zone) DO NOTHING
                ''', (zid, name, region_id))
                inserted[1] += cur.rowcount
                cur.execute('SELECT id_region, nom_zone FROM zone WHERE id_zone = %s', (zid,))
                if cur.fetchone() != (region_id, name):
                    raise RuntimeError(f'Zone #{zid} déjà présente avec un autre contenu.')

            for hid, name in sorted(data.habitats.items()):
                cur.execute('''
                    INSERT INTO habitat (id_habitat, nom_habitat)
                    VALUES (%s, %s)
                    ON CONFLICT (id_habitat) DO NOTHING
                ''', (hid, name))
                inserted[2] += cur.rowcount
                cur.execute('SELECT nom_habitat FROM habitat WHERE id_habitat = %s', (hid,))
                if cur.fetchone()[0] != name:
                    raise RuntimeError(f'Habitat #{hid} déjà présent avec un autre nom.')

            for pid, hid in sorted(data.species_habitats):
                cur.execute('''
                    INSERT INTO vivre_habitat (id_pokemon, id_habitat)
                    VALUES (%s, %s)
                    ON CONFLICT (id_pokemon, id_habitat) DO NOTHING
                ''', (pid, hid))
                inserted[3] += cur.rowcount

            for pid, zid in sorted(data.locations):
                # frequence_rencontre = NULL : pas de faux pourcentage global.
                cur.execute('''
                    INSERT INTO se_trouver (id_pokemon, id_zone, frequence_rencontre)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (id_pokemon, id_zone) DO NOTHING
                ''', (pid, zid))
                inserted[4] += cur.rowcount

            # Les IDs sont explicitement fournis depuis PokéAPI.
            # Les séquences doivent suivre le plus grand ID réellement présent.
            for table, column in (('region', 'id_region'), ('zone', 'id_zone'),
                                  ('habitat', 'id_habitat')):
                cur.execute(f'''
                    SELECT setval(
                        pg_get_serial_sequence('public.{table}', '{column}'),
                        COALESCE(MAX({column}), 1),
                        MAX({column}) IS NOT NULL
                    ) FROM public.{table}
                ''')
    return tuple(inserted)


def main() -> int:
    parser = argparse.ArgumentParser(description='Lot 4 : géographie et habitats de Kanto.')
    parser.add_argument('--dry-run', action='store_true', help='Télécharger et analyser sans toucher à PostgreSQL')
    parser.add_argument('--refresh', action='store_true', help='Rafraîchir le cache local PokéAPI')
    args = parser.parse_args()
    print(f'KANTO - géographie et habitats. Jeux de référence pour les rencontres : {", ".join(sorted(VERSIONS))}.')
    print('Aucune modification des tables Pokémon, capacités ou évolutions.')
    try:
        data = collect(PokeAPI(args.refresh), VERSIONS)
    except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as err:
        print(f'Collecte annulée, aucune écriture en base : {err}', file=sys.stderr)
        return 1
    print('\nDONNÉES COLLECTÉES :')
    print(f'  1 région ; {len(data.zones)} lieux ; {data.areas_count} sous-zones examinées')
    print(f'  {len(data.habitats)} habitats ; {len(data.species_habitats)} associations Pokémon/habitat')
    print(f'  {len(data.locations)} associations Pokémon/lieu pour les versions choisies')
    print(f'  {len(data.pokemon_without_habitat)} Pokémon sans habitat indiqué dans PokéAPI')
    if not data.locations:
        print('ATTENTION : aucune rencontre documentée pour ces versions ; SE_TROUVER restera inchangée.')
    if args.dry_run:
        print('DRY-RUN : aucune modification PostgreSQL.')
        return 0
    password = os.getenv('PGPASSWORD') or getpass.getpass('Mot de passe PostgreSQL : ')
    try:
        conn = psycopg.connect(host=os.getenv('PGHOST', 'localhost'),
                               port=os.getenv('PGPORT', '5432'),
                               user=os.getenv('PGUSER', 'postgres'),
                               dbname=DB_NAME, password=password,
                               connect_timeout=10, autocommit=True)
    except psycopg.Error as err:
        print(f'Connexion PostgreSQL impossible : {err}', file=sys.stderr)
        return 1
    try:
        preflight(conn)
        counts = persist(conn, data)
        print('\nBILAN :')
        for label, num in zip(('région', 'lieux', 'habitats', 'associations habitat', 'localisations'), counts):
            print(f'  {label} : {num} ajouté(s)')
        print('  APPARAITRE_REGION : cohérence assurée par RG07.')
        print('  ACCUEILLIR_HABITAT : non renseignée (pas de relation attestée).')
        print('SUCCÈS : géographie importée, sans modifier les Pokémon, évolutions et capacités.')
        return 0
    except (psycopg.Error, RuntimeError, ValueError) as err:
        print(f'ÉCHEC SQL : {err}', file=sys.stderr)
        print('Importation annulée : les écritures de la transaction ont été annulées.')
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
