#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compléter les évolutions des 151 Pokémon de Kanto depuis PokéAPI.

Tables : evolution, condition_evolution, etre_possible_si.
Aucune modification de schéma. Chaque évolution + ses conditions est transactionnelle
pour respecter RG12 (au moins une condition). Relançable sans doublonner.

Installation : py -m pip install requests "psycopg[binary]"
Exécution    : py import_pokedex_evolutions.py
Prévisualiser: py import_pokedex_evolutions.py --dry-run

Important : une entrée evolution_details PokéAPI est une ALTERNATIVE complète.
Les critères multiples de cette entrée sont CUMULATIFS et sont enregistrés
ensemble dans UNE SEULE ligne condition_evolution (notre MCD relie ces lignes
par un OU). Ne pas séparer ces critères en lignes indépendantes.
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
    sys.exit('Module psycopg absent : py -m pip install "psycopg[binary]"')

API_ROOT = 'https://pokeapi.co/api/v2'
DB_NAME = 'pokedex_dev'
CACHE_DIR = Path(__file__).resolve().parent / '.pokeapi_cache'
KANTO = frozenset(range(1, 152))

EVENT_LABELS = {
    'level-up': 'Montée de niveau',
    'use-item': "Utilisation d'un objet",
    'trade': 'Échange',
    'shed': 'Apparition liée à une évolution',
    'spin': 'Rotation',
    'tower-of-darkness': 'Épreuve de la tour des Ténèbres',
    'tower-of-waters': 'Épreuve de la tour des Eaux',
    'three-critical-hits': 'Trois coups critiques',
    'take-damage': 'Dégâts reçus',
    'agile-style-move': 'Capacité en style rapide',
    'strong-style-move': 'Capacité en style puissant',
    'recoil-damage': 'Dégâts de recul',
}

FIELD_LABELS = {
    'min_level': 'niveau minimum',
    'item': 'objet à utiliser',
    'held_item': 'objet tenu',
    'min_happiness': 'bonheur minimum',
    'min_affection': 'affection minimum',
    'min_beauty': 'beauté minimum',
    'gender': 'sexe requis',
    'known_move': 'capacité connue',
    'known_move_type': 'type de capacité connu',
    'location': 'lieu',
    'time_of_day': 'moment de la journée',
    'trade_species': 'Pokémon échangé',
    'party_species': "espèce présente dans l'équipe",
    'party_type': "type présent dans l'équipe",
    'relative_physical_stats': 'relation Attaque / Défense',
    'needs_overworld_rain': 'pluie nécessaire',
    'needs_multiplayer': 'multijoueur nécessaire',
    'near_special_rock': 'rocher spécial à proximité',
    'turn_upside_down': 'console retournée',
    'region': 'région requise',
    'required_pokemon_form': 'forme de départ requise',
    'evolved_pokemon_form': 'forme cible',
    'used_move': 'capacité utilisée',
    'min_move_count': "nombre minimum d'utilisations",
    'min_steps': 'nombre minimum de pas',
    'min_damage_taken': 'dégâts minimum reçus',
    'allowed_natures': 'natures autorisées',
    'condition_expression': 'expression conditionnelle',
}


class Api:
    def __init__(self, refresh: bool):
        self.refresh = refresh
        self.http = requests.Session()
        retry = Retry(total=4, connect=4, read=3, backoff_factor=0.8,
                      status_forcelist=(429, 500, 502, 503, 504))
        self.http.mount('https://', HTTPAdapter(max_retries=retry))
        self.http.headers['User-Agent'] = 'Pokedex-Looping-Evolutions/1.1 (educational use)'
        CACHE_DIR.mkdir(exist_ok=True)

    def get(self, path_or_url: str) -> dict:
        url = (path_or_url if path_or_url.startswith('https://')
               else f'{API_ROOT}/{path_or_url.lstrip("/")}')
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'pokeapi.co'
                or not parsed.path.startswith('/api/v2/')):
            raise ValueError(f'Adresse PokéAPI inattendue : {url}')

        # Même convention de cache que l'importeur des 151 Pokémon.
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]
        dest = CACHE_DIR / f'{cache_key}.json'
        if dest.is_file() and not self.refresh:
            try:
                value = json.loads(dest.read_text(encoding='utf-8'))
                if isinstance(value, dict):
                    return value
            except (OSError, ValueError):
                dest.unlink(missing_ok=True)

        response = self.http.get(url, timeout=(12, 35))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f'JSON inattendu : {url}')
        tmp = dest.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        tmp.replace(dest)
        time.sleep(0.1)
        return data


def resource_id(resource: dict) -> int:
    match = re.search(r'/([0-9]+)/?$', resource['url'])
    if not match:
        raise ValueError(f'Identifiant manquant dans la ressource : {resource}')
    return int(match.group(1))


def canonical_value(value) -> str:
    """Valeurs PokéAPI compactes et fidèles, sans conversion silencieuse."""
    if isinstance(value, dict) and 'name' in value:
        return str(value['name'])
    if isinstance(value, list):
        return ','.join(canonical_value(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'))
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def meaningful(value) -> bool:
    """Conserver 0 (ex. relative_physical_stats), ignorer null/false/vide."""
    return value is not None and value is not False and value != '' and value != []


@dataclass(frozen=True)
class Condition:
    type_condition: str
    valeur_condition: str | None
    description_condition: str


def make_condition(detail: dict) -> Condition:
    """Une option PokéAPI -> une condition atomique dans notre MCD (ET entre critères)."""
    trigger = detail.get('trigger')
    if not isinstance(trigger, dict) or not trigger.get('name'):
        raise ValueError('Détail PokéAPI sans déclencheur : vérification manuelle nécessaire.')
    event = str(trigger['name'])

    # Ces champs décrivent les versions de jeu, pas des conditions à cumuler.
    skip = {'trigger', 'is_default', 'version_group'}
    clauses = [(key, canonical_value(value)) for key, value in sorted(detail.items())
               if key not in skip and meaningful(value)]

    # L'origine reste identifiable même pour une condition sans paramètre.
    raw = '; '.join(f'{key}={value}' for key, value in clauses)
    pretty = ' ET '.join(f'{FIELD_LABELS.get(key, key)} : {value}'
                         for key, value in clauses)
    description = EVENT_LABELS.get(event, event)
    if pretty:
        description += ' ; conditions simultanées : ' + pretty
    else:
        description += ' (aucun autre critère fourni par PokéAPI)'

    # La colonne du modèle est VARCHAR(500) : interdiction de tronquer une condition.
    if len(description) > 500:
        raise ValueError(f'Condition trop longue ({len(description)} caractères) : {event}')
    if len(event) > 100:
        raise ValueError('Déclencheur trop long pour type_condition VARCHAR(100).')
    if not raw:
        val = None
    elif len(raw) <= 100:
        val = raw
    else:
        # Identifiant stable, détails intégraux dans description_condition.
        val = 'sha256:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]
    return Condition(type_condition=event.upper(), valeur_condition=val,
                     description_condition=description)


def details_for_edge(details: list, source_name: str, target_name: str) -> list[Condition]:
    """Accepter les formes normales, écarter les variantes régionales.

    PokéAPI précise parfois la forme normale de départ (ex. 'pikachu'
    pour Pikachu -> Raichu). Ce n'est PAS une forme régionale à exclure.
    En revanche, 'raichu-alola' ne correspond pas à notre POKEMON #26.
    """
    result: list[Condition] = []
    for entry in details:
        if not isinstance(entry, dict):
            raise ValueError('Détail d’évolution mal formé.')
        if entry.get('is_default') is False:
            continue

        required = entry.get('required_pokemon_form')
        evolved = entry.get('evolved_pokemon_form')
        if required is not None and (
            not isinstance(required, dict) or required.get('name') != source_name
        ):
            continue
        if evolved is not None and (
            not isinstance(evolved, dict) or evolved.get('name') != target_name
        ):
            continue

        # Les formes normales sont implicites ; elles ne constituent pas
        # des conditions d'évolution supplémentaires dans notre MCD.
        clean_entry = dict(entry)
        clean_entry.pop('required_pokemon_form', None)
        clean_entry.pop('evolved_pokemon_form', None)
        condition = make_condition(clean_entry)
        if condition not in result:
            result.append(condition)
    return result


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    chain: int
    conditions: tuple[Condition, ...]


def walk_chain(chain: dict, chain_id: int) -> list[Edge]:
    """Parcourir aussi les branches et les bébés non-Kanto pour trouver toutes les arêtes Kanto."""
    edges = []

    def visit(node: dict, parent: int | None, parent_name: str | None):
        target = resource_id(node['species'])
        target_name = node['species']['name']
        if parent is not None and parent in KANTO and target in KANTO:
            options = details_for_edge(
                node.get('evolution_details') or [], parent_name, target_name
            )
            if options:
                edges.append(Edge(parent, target, chain_id, tuple(options)))
            else:
                print(
                    f'\nAVERTISSEMENT : évolution #{parent} -> #{target} '
                    'ignorée (aucune condition pour la forme standard).',
                    file=sys.stderr,
                )
        for successor in node.get('evolves_to') or []:
            visit(successor, target, target_name)

    visit(chain['chain'], None, None)
    return edges


def fetch_edges(api: Api) -> list[Edge]:
    seen_chains = set()
    result: dict[int, Edge] = {}
    for species_id in range(1, 152):
        species = api.get(f'pokemon-species/{species_id}/')
        evolution_ref = species.get('evolution_chain')
        if not evolution_ref:
            continue
        chain_id = resource_id(evolution_ref)
        if chain_id in seen_chains:
            continue
        seen_chains.add(chain_id)
        chain = api.get(evolution_ref['url'])
        for edge in walk_chain(chain, chain_id):
            if edge.target in result:
                previous = result[edge.target]
                if previous.source != edge.source:
                    raise ValueError(
                        f'Le modèle n’admet qu’une source pour #{edge.target} : '
                        f'#{previous.source} et #{edge.source} (chaînes PokéAPI).'
                    )
                combined = tuple(dict.fromkeys(previous.conditions + edge.conditions))
                result[edge.target] = Edge(edge.source, edge.target, chain_id, combined)
            else:
                result[edge.target] = edge
        print(f'Chaîne #{chain_id} récupérée ({len(seen_chains)} chaînes)', end='\r', flush=True)
    print(' ' * 75, end='\r')
    return sorted(result.values(), key=lambda e: (e.source, e.target))


def preflight(conn) -> None:
    with conn.cursor() as cur:
        cur.execute('SELECT current_database()')
        if cur.fetchone()[0] != DB_NAME:
            raise RuntimeError('La base active n’est pas pokedex_dev : opération annulée.')
        for name in ('pokemon', 'evolution', 'condition_evolution', 'etre_possible_si'):
            cur.execute('SELECT to_regclass(%s)', (f'public.{name}',))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f'Table {name} absente. Import annulé.')
        cur.execute('SELECT id_pokemon FROM pokemon WHERE id_pokemon BETWEEN 1 AND 151')
        present = {row[0] for row in cur.fetchall()}
        missing = sorted(KANTO - present)
        if missing:
            raise RuntimeError(
                f'{len(missing)} Pokémon Kanto absents (ex. {missing[:12]}). '
                "Terminez d'abord l'import initial des 151 Pokémon."
            )


def upsert_one(conn, edge: Edge) -> tuple[bool, int]:
    """Une transaction par liaison, avec zéro effacement de données existantes."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO evolution (id_pokemon_source, id_pokemon_cible, commentaire_evolution)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_pokemon_cible) DO NOTHING
                RETURNING id_evolution
            ''', (edge.source, edge.target, f'Source : PokéAPI, chaîne #{edge.chain}'))
            inserted_row = cur.fetchone()
            if inserted_row:
                evo_id = inserted_row[0]
                created = True
            else:
                cur.execute('''
                    SELECT id_evolution, id_pokemon_source FROM evolution
                    WHERE id_pokemon_cible = %s
                ''', (edge.target,))
                current = cur.fetchone()
                if not current or current[1] != edge.source:
                    raise ValueError(
                        f'Conflit EVOLUTION pour la cible #{edge.target} : '
                        'source différente, aucune écriture effectuée.'
                    )
                evo_id = current[0]
                created = False

            added = 0
            for option in edge.conditions:
                cur.execute('''
                    SELECT id_condition
                    FROM condition_evolution
                    WHERE type_condition = %s
                      AND valeur_condition IS NOT DISTINCT FROM %s
                      AND description_condition IS NOT DISTINCT FROM %s
                    ORDER BY id_condition
                    LIMIT 1
                ''', (option.type_condition, option.valeur_condition,
                      option.description_condition))
                found = cur.fetchone()
                if found:
                    condition_id = found[0]
                else:
                    cur.execute('''
                        INSERT INTO condition_evolution (
                            type_condition, valeur_condition, description_condition
                        ) VALUES (%s, %s, %s) RETURNING id_condition
                    ''', (option.type_condition, option.valeur_condition,
                          option.description_condition))
                    condition_id = cur.fetchone()[0]

                cur.execute('''
                    INSERT INTO etre_possible_si (id_evolution, id_condition)
                    VALUES (%s, %s)
                    ON CONFLICT (id_evolution, id_condition) DO NOTHING
                    RETURNING id_condition
                ''', (evo_id, condition_id))
                if cur.fetchone():
                    added += 1
    return created, added


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Importer les évolutions Kanto de PokéAPI dans pokedex_dev.'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Prévisualiser les évolutions sans écrire dans PostgreSQL')
    parser.add_argument('--refresh', action='store_true',
                        help='Rafraîchir les réponses PokéAPI (ignorer le cache)')
    args = parser.parse_args()

    print('Import ÉVOLUTIONS KANTO (151 espèces) - aucune table modifiée ou supprimée.')
    api = Api(refresh=args.refresh)
    try:
        edges = fetch_edges(api)
    except (requests.RequestException, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Récupération PokéAPI interrompue : {exc}', file=sys.stderr)
        return 1

    print(f'Évolutions Kanto éligibles : {len(edges)}')
    for edge in edges:
        descriptions = ' OU '.join(c.description_condition for c in edge.conditions)
        print(f'  #{edge.source:03d} -> #{edge.target:03d} : {descriptions}')

    if args.dry_run:
        print('\nPrévisualisation uniquement : aucune écriture en base.')
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

    new_evolutions = new_links = already = 0
    failed: list[tuple[int, str]] = []
    try:
        preflight(conn)
        for n, edge in enumerate(edges, 1):
            try:
                created, added = upsert_one(conn, edge)
                new_evolutions += int(created)
                new_links += added
                already += int(not created and not added)
                print(f'[{n}/{len(edges)}] OK #{edge.source:03d} -> #{edge.target:03d}'
                      f' ({added} condition(s) ajoutée(s))', flush=True)
            except (psycopg.Error, ValueError) as exc:
                failed.append((edge.target, str(exc)))
                print(f'[{n}/{len(edges)}] ERREUR cible #{edge.target:03d}: {exc}',
                      file=sys.stderr, flush=True)
        print('\nBILAN :', new_evolutions, 'évolutions créées,',
              new_links, 'liens de conditions ajoutés,',
              already, 'évolutions déjà complètes,',
              len(failed), 'erreurs.')
        if failed:
            for target, err in failed:
                print(f'  cible #{target}: {err}', file=sys.stderr)
        print('Les autres tables ne sont pas modifiées. Import relançable.')
        return 2 if failed else 0
    except (psycopg.Error, RuntimeError) as exc:
        print(f'ARRÊT : {exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
