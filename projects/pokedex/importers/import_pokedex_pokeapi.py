#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Importe les espèces PokéAPI dans le schéma PostgreSQL Pokédex issu de Looping.

Par défaut : Pokémon nationaux 1 à 151, forme par défaut de chaque espèce.
Aucun DROP TABLE, ALTER TABLE ou CREATE TABLE. Chaque Pokémon et ses types/talents
sont enregistrés dans une même transaction (RG10 et RG13).

Dépendances : py -m pip install requests "psycopg[binary]"
Exécution   : py import_pokedex_pokeapi.py --start 1 --end 151
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
    sys.exit('Module psycopg manquant. Installez-le : py -m pip install "psycopg[binary]"')

API_BASE = 'https://pokeapi.co/api/v2'
DB_NAME = 'pokedex_dev'
CACHE_DIR = Path(__file__).resolve().parent / '.pokeapi_cache'
STATS = {
    'hp': 'pv_base',
    'attack': 'attaque_base',
    'defense': 'defense_base',
    'special-attack': 'attaque_speciale',
    'special-defense': 'defense_speciale',
    'speed': 'vitesse_base',
}


def clean(value: str | None, max_length: int) -> str | None:
    if not value:
        return None
    normalized = re.sub(r'\s+', ' ', value.replace('\u00ad', '')).strip()
    return normalized[:max_length] or None


def french_entry(entries: list, field: str) -> str | None:
    """Préférer le français ; utiliser l'anglais en dernier recours."""
    for lang in ('fr', 'en'):
        for entry in reversed(entries or []):
            if entry.get('language', {}).get('name') == lang:
                value = entry.get(field)
                if value and value.strip():
                    return value
    return None


def resource_id(resource: dict) -> int:
    match = re.search(r'/([0-9]+)/?$', resource['url'])
    if not match:
        raise ValueError(f"Identifiant PokéAPI absent : {resource['url']}")
    return int(match.group(1))


def roman(num: int) -> str:
    result = ''
    for v, sym in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                   (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                   (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while num >= v:
            result += sym
            num -= v
    return result


class PokeAPI:
    def __init__(self, refresh: bool = False):
        self.refresh = refresh
        self.session = requests.Session()
        retry = Retry(total=4, connect=4, read=3, backoff_factor=0.8,
                      status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.headers['User-Agent'] = 'Pokedex-Looping-Importer/1.0 (educational use)'
        CACHE_DIR.mkdir(exist_ok=True)

    def get(self, path_or_url: str) -> dict:
        url = path_or_url if path_or_url.startswith('https://') else f'{API_BASE}/{path_or_url.lstrip("/")}'
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'pokeapi.co' or not parsed.path.startswith('/api/v2/'):
            raise ValueError(f'URL non autorisée : {url}')
        key = hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]
        cache_path = CACHE_DIR / f'{key}.json'
        if cache_path.is_file() and not self.refresh:
            try:
                return json.loads(cache_path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                cache_path.unlink(missing_ok=True)
        response = self.session.get(url, timeout=(12, 35))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f'Réponse inattendue pour {url}')
        temp_path = cache_path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temp_path.replace(cache_path)
        time.sleep(0.10)  # Courtoisie envers le service public PokéAPI.
        return data


def build_pokemon(api: PokeAPI, species_id: int) -> dict:
    species = api.get(f'pokemon-species/{species_id}/')
    varieties = species.get('varieties', [])
    default_variety = next((v for v in varieties if v.get('is_default')), None)
    if default_variety is None:
        raise ValueError('Cette espèce ne possède pas de variété par défaut.')
    pokemon = api.get(default_variety['pokemon']['url'])

    names = species.get('names', [])
    name = clean(french_entry(names, 'name') or species.get('name'), 100)
    category = clean(french_entry(species.get('genera', []), 'genus') or 'Pokémon', 100)
    description = clean(french_entry(species.get('flavor_text_entries', []), 'flavor_text'), 1000)
    generation = resource_id(species['generation'])

    stats_by_name = {s['stat']['name']: s['base_stat'] for s in pokemon.get('stats', [])}
    if not all(stat in stats_by_name and stats_by_name[stat] > 0 for stat in STATS):
        raise ValueError('Statistiques de base incomplètes ou invalides.')

    type_rows = []
    for item in sorted(pokemon.get('types', []), key=lambda t: t['slot']):
        type_id = resource_id(item['type'])
        detail = api.get(item['type']['url'])
        type_name = clean(french_entry(detail.get('names', []), 'name') or detail['name'], 50)
        type_rows.append((type_id, type_name, item['slot']))
    if not 1 <= len(type_rows) <= 2:
        raise ValueError(f'Nombre de types invalide : {len(type_rows)}')

    ability_rows = []
    for item in pokemon.get('abilities', []):
        ability_id = resource_id(item['ability'])
        detail = api.get(item['ability']['url'])
        ability_name = clean(french_entry(detail.get('names', []), 'name') or detail['name'], 100)
        ability_desc = clean(french_entry(detail.get('flavor_text_entries', []), 'flavor_text'), 500)
        ability_rows.append((ability_id, ability_name, ability_desc, bool(item['is_hidden'])))
    if not 1 <= len(ability_rows) <= 3 or sum(a[3] for a in ability_rows) > 1:
        raise ValueError('Nombre de talents ou talents cachés invalide.')

    sprites = pokemon.get('sprites') or {}
    official = (sprites.get('other') or {}).get('official-artwork') or {}
    image = clean(official.get('front_default') or sprites.get('front_default'), 500)
    height_dm = pokemon.get('height', 0)
    weight_hg = pokemon.get('weight', 0)
    if height_dm <= 0 or weight_hg < 0:
        raise ValueError('Taille ou poids invalide.')

    return {
        'id': species_id,
        'name': name,
        'category': category,
        'description': description,
        'height': height_dm / 10,  # PokéAPI : décimètres -> mètres
        'weight': weight_hg / 10,  # PokéAPI : hectogrammes -> kilogrammes
        'image': image,
        'generation': generation,
        'stats': stats_by_name,
        'types': type_rows,
        'abilities': ability_rows,
    }


def save_pokemon(conn, p: dict) -> None:
    """Une transaction autonome par Pokémon : aucune violation RG10/RG13 au COMMIT."""
    with conn.transaction():
        with conn.cursor() as cur:
            gen = p['generation']
            cur.execute('''
                INSERT INTO generation (id_generation, numero_generation, nom_generation)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_generation) DO UPDATE SET
                    numero_generation = EXCLUDED.numero_generation,
                    nom_generation = EXCLUDED.nom_generation
            ''', (gen, gen, f'Génération {roman(gen)}'))

            for type_id, type_name, slot in p['types']:
                cur.execute('''
                    INSERT INTO type (id_type, nom_type) VALUES (%s, %s)
                    ON CONFLICT (id_type) DO UPDATE SET nom_type = EXCLUDED.nom_type
                ''', (type_id, type_name))

            for ability_id, ability_name, ability_desc, hidden in p['abilities']:
                cur.execute('''
                    INSERT INTO talent (id_talent, nom_talent, description_talent)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_talent) DO UPDATE SET
                        nom_talent = EXCLUDED.nom_talent,
                        description_talent = EXCLUDED.description_talent
                ''', (ability_id, ability_name, ability_desc))

            s = p['stats']
            cur.execute('''
                INSERT INTO pokemon (
                    id_pokemon, nom_pokemon, categorie_pokedex, description_pokedex,
                    taille_m, poids_kg, url_image, pv_base, attaque_base,
                    defense_base, attaque_speciale, defense_speciale, vitesse_base,
                    id_generation
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id_pokemon) DO UPDATE SET
                    nom_pokemon = EXCLUDED.nom_pokemon,
                    categorie_pokedex = EXCLUDED.categorie_pokedex,
                    description_pokedex = EXCLUDED.description_pokedex,
                    taille_m = EXCLUDED.taille_m,
                    poids_kg = EXCLUDED.poids_kg,
                    url_image = EXCLUDED.url_image,
                    pv_base = EXCLUDED.pv_base,
                    attaque_base = EXCLUDED.attaque_base,
                    defense_base = EXCLUDED.defense_base,
                    attaque_speciale = EXCLUDED.attaque_speciale,
                    defense_speciale = EXCLUDED.defense_speciale,
                    vitesse_base = EXCLUDED.vitesse_base,
                    id_generation = EXCLUDED.id_generation
            ''', (
                p['id'], p['name'], p['category'], p['description'],
                p['height'], p['weight'], p['image'],
                s['hp'], s['attack'], s['defense'], s['special-attack'],
                s['special-defense'], s['speed'], gen
            ))

            # Remplacer intégralement les associations de cette espèce.
            # Les contrôles RG10/RG13 sont différés jusqu'au COMMIT.
            cur.execute('DELETE FROM posseder_type WHERE id_pokemon = %s', (p['id'],))
            cur.execute('DELETE FROM avoir_talent WHERE id_pokemon = %s', (p['id'],))
            for type_id, _type_name, slot in p['types']:
                cur.execute('''
                    INSERT INTO posseder_type (id_pokemon, id_type, position_type)
                    VALUES (%s, %s, %s)
                ''', (p['id'], type_id, slot))
            for ability_id, _name, _desc, hidden in p['abilities']:
                cur.execute('''
                    INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache)
                    VALUES (%s, %s, %s)
                ''', (p['id'], ability_id, hidden))


def adjust_sequences(conn) -> None:
    """Après les IDs PokéAPI explicites, réaligner les séquences SERIAL."""
    with conn.transaction():
        with conn.cursor() as cur:
            for table, id_col in (('generation', 'id_generation'),
                                  ('type', 'id_type'),
                                  ('talent', 'id_talent'),
                                  ('pokemon', 'id_pokemon')):
                cur.execute(f'''
                    SELECT setval(
                        pg_get_serial_sequence('public.{table}', '{id_col}'),
                        COALESCE(MAX({id_col}), 1),
                        MAX({id_col}) IS NOT NULL
                    ) FROM public.{table}
                ''')


def species_ids(api: PokeAPI, all_species: bool, start: int, end: int) -> list[int]:
    if not all_species:
        return list(range(start, end + 1))
    ids = []
    url = f'{API_BASE}/pokemon-species/?limit=200&offset=0'
    while url:
        page = api.get(url)
        ids.extend(resource_id(item) for item in page.get('results', []))
        url = page.get('next')
    return sorted(set(ids))


def main() -> int:
    parser = argparse.ArgumentParser(description='Importer les Pokémon de PokéAPI dans pokedex_dev.')
    parser.add_argument('--start', type=int, default=1, help='Premier numéro national (défaut : 1)')
    parser.add_argument('--end', type=int, default=151, help='Dernier numéro national (défaut : 151)')
    parser.add_argument('--all', action='store_true', help='Toutes les espèces actuellement listées par PokéAPI')
    parser.add_argument('--refresh', action='store_true', help='Ignorer le cache JSON existant')
    args = parser.parse_args()
    if args.start < 1 or args.end < args.start:
        parser.error('--start et --end doivent constituer une plage positive valide.')

    print(f'Import dans {DB_NAME} : aucun changement de schéma et aucun effacement de table.')
    api = PokeAPI(refresh=args.refresh)
    try:
        ids = species_ids(api, args.all, args.start, args.end)
    except Exception as exc:
        print(f'Échec de connexion à PokéAPI : {exc}', file=sys.stderr)
        return 1

    password = os.getenv('PGPASSWORD') or getpass.getpass('Mot de passe PostgreSQL : ')
    try:
        conn = psycopg.connect(
            host=os.getenv('PGHOST', 'localhost'),
            port=os.getenv('PGPORT', '5432'),
            dbname=DB_NAME,
            user=os.getenv('PGUSER', 'postgres'),
            password=password,
            connect_timeout=10,
            autocommit=True,
        )
    except psycopg.Error as exc:
        print(f'Connexion PostgreSQL impossible : {exc}', file=sys.stderr)
        return 1

    succeeded, failed = 0, []
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT current_database()')
            if cur.fetchone()[0] != DB_NAME:
                raise RuntimeError('Base PostgreSQL inattendue : import annulé.')
            for table in ('generation', 'pokemon', 'type', 'talent', 'posseder_type', 'avoir_talent'):
                cur.execute('SELECT to_regclass(%s)', (f'public.{table}',))
                if cur.fetchone()[0] is None:
                    raise RuntimeError(f'Table absente : {table}. Installez le schéma Looping avant import.')

        for ix, species_id in enumerate(ids, 1):
            try:
                p = build_pokemon(api, species_id)
                save_pokemon(conn, p)
                succeeded += 1
                print(f'[{ix}/{len(ids)}] OK #{species_id:04d} {p["name"]}', flush=True)
            except (requests.RequestException, psycopg.Error, ValueError, KeyError, TypeError) as exc:
                failed.append(species_id)
                print(f'[{ix}/{len(ids)}] ERREUR #{species_id:04d} : {exc}', file=sys.stderr, flush=True)

        if succeeded:
            adjust_sequences(conn)
        print(f'\nBILAN : {succeeded} Pokémon importés, {len(failed)} échec(s).')
        if failed:
            print('À relancer pour ces numéros : ' + ', '.join(map(str, failed)))
        print('Aucune table supprimée. Les transactions échouées ont été annulées.')
        return 0 if not failed else 2
    except (psycopg.Error, RuntimeError) as exc:
        print(f'Arrêt : {exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
