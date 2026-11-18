#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Peupler CAPACITE, METHODE_APPRENTISSAGE et APPRENDRE_CAPACITE (Kanto).

Référentiel des apprentissages : Pokémon Rouge/Bleu (PokéAPI : red-blue).
Ne modifie ni les tables, ni les Pokémon, ni les évolutions existantes.

Installation : py -m pip install requests "psycopg[binary]"
Prévisualiser : py ./import_pokedex_capacites.py --dry-run
Importer     : py ./import_pokedex_capacites.py

ATTENTION au modèle Looping : la clé (pokemon, methode, capacite) ne permet
qu'un niveau par triplet. Pour une même capacité apprise plusieurs fois par
la même méthode, seul le plus petit niveau strictement positif est retenu.
Les capacités de départ (level-up avec niveau 0) sont associées à DEPART,
avec niveau_apprentissage NULL, afin de respecter RG09 sans inventer un niveau.
Les statistiques des capacités reflètent la fiche PokéAPI actuelle (et non
nécessairement les valeurs historiques Rouge/Bleu).
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
    sys.exit('Module manquant : py -m pip install "psycopg[binary]"')

DB_NAME = 'pokedex_dev'
BASE = 'https://pokeapi.co/api/v2'
VERSION_GROUP = 'red-blue'
CACHE_DIR = Path(__file__).resolve().parent / '.pokeapi_cache'

# Codes normalisés pour notre RG09 (NIVEAU exige un entier >= 1).
METHODS = {
    'level-up': ('NIVEAU', 'Apprentissage par montée de niveau.'),
    'machine': ('MACHINE', 'Apprentissage par CT ou CS (machine).'),
    'egg': ('REPRODUCTION', 'Apprentissage par reproduction.'),
    'tutor': ('TUTEUR', 'Apprentissage auprès d’un maître des capacités.'),
    'stadium-surfing-pikachu': ('STADIUM_SURF', 'Capacité liée à Pokémon Stadium.'),
    'light-ball-egg': ('OEUF_BALLE_LUMIERE', 'Capacité issue d’un œuf avec Balle Lumière.'),
    'form-change': ('CHANGEMENT_FORME', 'Apprentissage par changement de forme.'),
}

# L'ID négatif est volontaire : réservé à une méthode déduite du niveau 0.
START_METHOD_ID = -1
START_METHOD = ('DEPART', 'Capacité initiale : niveau 0 indiqué par PokéAPI.')
DAMAGE_CLASSES = {'physical': 'PHYSIQUE', 'special': 'SPECIALE', 'status': 'STATUT'}


def normalize_text(raw: str | None, limit: int) -> str | None:
    if not isinstance(raw, str):
        return None
    text = re.sub(r'\s+', ' ', raw.replace('\u00ad', '')).strip()
    return text[:limit] or None


def localized(items: list, field: str) -> str | None:
    for language in ('fr', 'en'):
        for entry in reversed(items or []):
            if entry.get('language', {}).get('name') == language:
                value = entry.get(field)
                if isinstance(value, str) and value.strip():
                    return value
    return None


def resource_id(resource: dict) -> int:
    match = re.search(r'/([0-9]+)/?$', resource['url'])
    if not match:
        raise ValueError(f'Ressource PokéAPI sans ID numérique : {resource}')
    return int(match.group(1))


class PokeAPI:
    def __init__(self, refresh: bool = False):
        self.refresh = refresh
        self.session = requests.Session()
        retry = Retry(total=4, connect=4, read=3, backoff_factor=0.8,
                      status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.headers['User-Agent'] = 'Pokedex-Looping-Moves/1.0 (educational use)'
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, path_or_url: str) -> dict:
        url = (path_or_url if path_or_url.startswith('https://')
               else f'{BASE}/{path_or_url.lstrip("/")}')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'pokeapi.co' or not parsed.path.startswith('/api/v2/'):
            raise ValueError(f'URL refusée : {url}')
        path = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.json')
        if path.is_file() and not self.refresh:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                path.unlink(missing_ok=True)
        response = self.session.get(url, timeout=(12, 35))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f'Réponse JSON inattendue : {url}')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temp.replace(path)
        time.sleep(.1)
        return data


def method_for(entry: dict) -> tuple[int, str, str, int | None]:
    """Retourne (id_methode, nom, description, niveau) compatibles avec RG09."""
    method = entry.get('move_learn_method')
    if not isinstance(method, dict):
        raise ValueError('Méthode d’apprentissage absente dans PokéAPI.')
    name = method.get('name')
    method_id = resource_id(method)
    level = entry.get('level_learned_at')
    if name == 'level-up':
        if not isinstance(level, int) or level < 0:
            raise ValueError(f'Niveau impossible : {level!r}')
        if level == 0:
            return START_METHOD_ID, *START_METHOD, None
        return method_id, *METHODS['level-up'], level
    code, description = METHODS.get(name, (str(name).upper().replace('-', '_'),
        f'Méthode PokéAPI : {name}'))
    if not code or len(code) > 50:
        raise ValueError(f'Nom de méthode invalide : {name}')
    return method_id, code, description[:255], None


def reduce_links(api: PokeAPI, start: int, end: int):
    """Tout récupérer AVANT la première écriture en base."""
    methods: dict[int, tuple[str, str]] = {}
    # (id_pokemon, id_methode, id_capacite) => niveau minimal ou NULL
    links: dict[tuple[int, int, int], int | None] = {}
    move_urls: dict[int, str] = {}
    without_moves: list[int] = []
    duplicate_levels = 0

    for n, poke_id in enumerate(range(start, end + 1), 1):
        species = api.get(f'pokemon-species/{poke_id}/')
        default = next((v for v in species.get('varieties', []) if v.get('is_default')), None)
        if not default:
            raise ValueError(f'Pokémon #{poke_id} : aucune forme par défaut.')
        pokemon = api.get(default['pokemon']['url'])
        found_here = 0
        for move_item in pokemon.get('moves', []):
            move_resource = move_item.get('move')
            if not move_resource:
                raise ValueError(f'Pokémon #{poke_id} : capacité sans référence.')
            move_id = resource_id(move_resource)
            for entry in move_item.get('version_group_details', []):
                if entry.get('version_group', {}).get('name') != VERSION_GROUP:
                    continue
                method_id, code, description, level = method_for(entry)
                if method_id in methods and methods[method_id][0] != code:
                    raise ValueError(f'ID de méthode {method_id} incohérent.')
                methods[method_id] = (code, description)
                move_urls[move_id] = move_resource['url']
                key = (poke_id, method_id, move_id)
                if key in links:
                    duplicate_levels += 1
                    previous = links[key]
                    if level is not None and (previous is None or level < previous):
                        links[key] = level
                else:
                    links[key] = level
                found_here += 1
        if not found_here:
            without_moves.append(poke_id)
        print(f'[{n:3d}/{end-start+1}] #{poke_id:03d} : {found_here} apprentissage(s) {VERSION_GROUP}', flush=True)

    if not links:
        raise ValueError(f'Aucun apprentissage disponible pour {VERSION_GROUP}.')
    if without_moves:
        raise ValueError('Aucun apprentissage Rouge/Bleu pour ces Pokémon : '
                         + ', '.join(str(x) for x in without_moves)
                         + '. Importation annulée pour éviter un jeu de données incomplet.')

    moves: dict[int, tuple] = {}
    for n, (move_id, url) in enumerate(sorted(move_urls.items()), 1):
        obj = api.get(url)
        label = normalize_text(localized(obj.get('names', []), 'name') or obj.get('name'), 100)
        description = normalize_text(localized(obj.get('flavor_text_entries', []), 'flavor_text'), 500)
        damage_class = obj.get('damage_class') or {}
        category = DAMAGE_CLASSES.get(damage_class.get('name'))
        power = obj.get('power')
        accuracy = obj.get('accuracy')
        pp = obj.get('pp')
        if not label or not category:
            raise ValueError(f'Capacité #{move_id} : nom ou catégorie invalide.')
        if power is not None and (not isinstance(power, int) or power < 0):
            raise ValueError(f'Capacité #{move_id} : puissance invalide {power}.')
        if accuracy is not None and (not isinstance(accuracy, int) or not 1 <= accuracy <= 100):
            raise ValueError(f'Capacité #{move_id} : précision invalide {accuracy}.')
        if pp is not None and (not isinstance(pp, int) or pp <= 0):
            raise ValueError(f'Capacité #{move_id} : PP invalides {pp}.')
        moves[move_id] = (label, description, category, power, accuracy, pp)
        if n % 25 == 0 or n == len(move_urls):
            print(f'Capacités détaillées : {n}/{len(move_urls)}', flush=True)

    # La table CAPACITE exige des noms uniques en français.
    reverse_names: dict[str, int] = {}
    for move_id, item in moves.items():
        name = item[0]
        if name in reverse_names and reverse_names[name] != move_id:
            raise ValueError(f'Nom français identique pour deux capacités : {name}, '
                             f'IDs {reverse_names[name]} et {move_id}.')
        reverse_names[name] = move_id

    return methods, links, moves, duplicate_levels


def preflight(conn, start: int, end: int) -> None:
    with conn.cursor() as cur:
        cur.execute('SELECT current_database()')
        if cur.fetchone()[0] != DB_NAME:
            raise RuntimeError('Mauvaise base active : opération annulée.')
        for table in ('pokemon', 'capacite', 'methode_apprentissage', 'apprendre_capacite'):
            cur.execute('SELECT to_regclass(%s)', (f'public.{table}',))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f'Table manquante : {table}')
        cur.execute('SELECT id_pokemon FROM pokemon WHERE id_pokemon BETWEEN %s AND %s', (start, end))
        present = {row[0] for row in cur.fetchall()}
        missing = sorted(set(range(start, end + 1)) - present)
        if missing:
            raise RuntimeError(f'Pokémon absents de la base : {missing[:20]}')


def save_all(conn, methods: dict, links: dict, moves: dict) -> tuple[int, int, int]:
    inserted_methods = inserted_moves = inserted_links = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for method_id, (code, desc) in sorted(methods.items()):
                cur.execute('''
                    INSERT INTO methode_apprentissage (id_methode, nom_methode, description_methode)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_methode) DO NOTHING
                ''', (method_id, code, desc))
                inserted_methods += cur.rowcount
                cur.execute('SELECT nom_methode FROM methode_apprentissage WHERE id_methode = %s', (method_id,))
                existing = cur.fetchone()[0]
                if existing != code:
                    raise RuntimeError(f'Méthode {method_id} : nom présent {existing!r}, attendu {code!r}.')

            for move_id, (name, description, category, power, accuracy, pp) in sorted(moves.items()):
                cur.execute('''
                    INSERT INTO capacite (
                        id_capacite, nom_capacite, description_capacite,
                        categorie, puissance, precision_capacite, points_pouvoir
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id_capacite) DO NOTHING
                ''', (move_id, name, description, category, power, accuracy, pp))
                inserted_moves += cur.rowcount
                cur.execute('SELECT nom_capacite FROM capacite WHERE id_capacite = %s', (move_id,))
                existing = cur.fetchone()[0]
                if existing != name:
                    raise RuntimeError(f'Capacité {move_id} : nom présent {existing!r}, attendu {name!r}.')

            for (poke_id, method_id, move_id), level in sorted(links.items()):
                cur.execute('''
                    INSERT INTO apprendre_capacite (
                        id_pokemon, id_methode, id_capacite, niveau_apprentissage
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id_pokemon, id_methode, id_capacite) DO NOTHING
                ''', (poke_id, method_id, move_id, level))
                inserted_links += cur.rowcount
    return inserted_methods, inserted_moves, inserted_links


def adjust_sequences(conn):
    # Les ID explicites ne font pas avancer automatiquement les séquences SERIAL.
    # Le setval est exécuté seulement une fois le lot inséré avec succès.
    with conn.transaction():
        with conn.cursor() as cur:
            for table, column in (('capacite', 'id_capacite'),
                                  ('methode_apprentissage', 'id_methode')):
                cur.execute(f'''
                    SELECT setval(
                        pg_get_serial_sequence('public.{table}', '{column}'),
                        COALESCE(MAX({column}), 1),
                        MAX({column}) IS NOT NULL
                    ) FROM public.{table}
                ''')


def main() -> int:
    parser = argparse.ArgumentParser(description='Capacités PokéAPI pour Kanto - Rouge/Bleu.')
    parser.add_argument('--dry-run', action='store_true', help='Préparer sans écrire dans PostgreSQL')
    parser.add_argument('--refresh', action='store_true', help='Ignorer le cache JSON local')
    parser.add_argument('--start', type=int, default=1, help='Premier Pokémon (défaut 1)')
    parser.add_argument('--end', type=int, default=151, help='Dernier Pokémon (défaut 151)')
    args = parser.parse_args()
    if not (1 <= args.start <= args.end <= 151):
        parser.error('Sélectionnez une plage de 1 à 151.')
    print(f'CAPACITÉS KANTO - groupe de versions {VERSION_GROUP}.')
    print('Aucune suppression, aucun changement de structure, aucune modification des évolutions.')

    try:
        methods, links, moves, reduced = reduce_links(PokeAPI(args.refresh), args.start, args.end)
    except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'IMPORT ANNULÉ (récupération des données) : {exc}', file=sys.stderr)
        return 1

    print(f'\nÀ importer : {len(moves)} capacités, {len(methods)} méthodes, '
          f'{len(links)} relations (niveaux répétés regroupés : {reduced}).')
    if args.dry_run:
        print('DRY-RUN : aucune modification PostgreSQL.')
        return 0

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

    try:
        preflight(conn, args.start, args.end)
        counts = save_all(conn, methods, links, moves)
        adjust_sequences(conn)
        print('\nBILAN :')
        print(f'  {counts[0]} méthodes ajoutées ; {len(methods) - counts[0]} déjà présentes.')
        print(f'  {counts[1]} capacités ajoutées ; {len(moves) - counts[1]} déjà présentes.')
        print(f'  {counts[2]} associations ajoutées ; {len(links) - counts[2]} déjà présentes.')
        print('SUCCÈS : les Pokémon et les évolutions existants sont inchangés.')
        return 0
    except (psycopg.Error, RuntimeError, ValueError) as exc:
        print(f'IMPORT ANNULÉ / ÉCHEC SQL : {exc}', file=sys.stderr)
        print('Les modifications du lot en cours ont été annulées si la transaction a échoué.')
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
