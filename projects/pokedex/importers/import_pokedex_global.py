#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Extension multi-generations du Pokedex Looping / PostgreSQL depuis PokeAPI.

DEPEND DES QUATRE IMPORTEURS deja utilises, dans le MEME DOSSIER :
  import_pokedex_pokeapi.py, import_pokedex_evolutions.py,
  import_pokedex_capacites.py, import_pokedex_geographie.py

Lancement Windows:
  py -m pip install requests "psycopg[binary]"
  py .\import_pokedex_global.py --phase pokemon
  py .\import_pokedex_global.py --phase evolutions
  py .\import_pokedex_global.py --phase capacites
  py .\import_pokedex_global.py --phase geographie
  py .\import_pokedex_global.py --phase tout

--phase tout execute les phases dans l'ordre. Par defaut : pokemon seulement.
Les donnees de plusieurs jeux sont fusionnees POUR LES APPRENTISSAGES ET RENCONTRES
car le schema Looping ne contient aucun champ version de jeu. Cette aggregation
ne doit pas etre interpretee comme la liste des capacites d'une edition precise.
Ne supprime aucune table, n'efface pas TOMS ni ses captures. Import relancable.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

try:
    import import_pokedex_pokeapi as pk
    import import_pokedex_evolutions as ev
    import import_pokedex_capacites as ca
    import import_pokedex_geographie as geo
except (ImportError, SystemExit) as exc:
    sys.exit(
        'Impossible de charger les importeurs existants. Placez ce fichier dans '
        'le meme dossier que import_pokedex_pokeapi.py, '
        'import_pokedex_evolutions.py, import_pokedex_capacites.py '
        'et import_pokedex_geographie.py.\nDetails : ' + str(exc)
    )

DB_NAME = 'pokedex_dev'
REQUIRED = (
    'pokemon', 'generation', 'type', 'talent', 'posseder_type', 'avoir_talent',
    'evolution', 'condition_evolution', 'etre_possible_si',
    'capacite', 'methode_apprentissage', 'apprendre_capacite',
    'region', 'zone', 'habitat', 'vivre_habitat', 'se_trouver', 'apparaitre_region',
)


def connection():
    password = os.getenv('PGPASSWORD') or getpass.getpass('Mot de passe PostgreSQL : ')
    conn = pk.psycopg.connect(
        dbname=DB_NAME,
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'),
        user=os.getenv('PGUSER', 'postgres'),
        password=password,
        connect_timeout=12,
        autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute('SELECT current_database()')
        if cur.fetchone()[0] != DB_NAME:
            raise RuntimeError('Mauvaise base PostgreSQL, import annule.')
        for table in REQUIRED:
            cur.execute('SELECT to_regclass(%s)', (f'public.{table}',))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f'Table manquante : public.{table}')
    return conn


def available_species(api):
    ids = pk.species_ids(api, True, 1, 151)
    if not ids:
        raise RuntimeError('PokéAPI n\'a retourne aucune espece.')
    return ids


def existing_ids(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT id_pokemon FROM pokemon')
        return {row[0] for row in cur.fetchall()}


def update_sequences(conn, table_cols):
    # Les identifiants explicites PokeAPI ne font pas avancer SERIAL.
    with conn.transaction():
        with conn.cursor() as cur:
            for table, col in table_cols:
                cur.execute(f"""
                    SELECT setval(pg_get_serial_sequence('public.{table}', '{col}'),
                                  GREATEST(COALESCE(MAX({col}), 1), 1),
                                  MAX({col}) IS NOT NULL)
                    FROM public.{table}
                """)


def import_species(conn, api, ids, refresh_existing=False):
    previously = existing_ids(conn)
    skipped = 0
    done = 0
    errors = []
    print(f'\n[POKEMON] {len(ids)} especes listees ; {len(previously)} deja en base.')
    for i, sid in enumerate(ids, 1):
        if sid in previously and not refresh_existing:
            skipped += 1
            continue
        try:
            payload = pk.build_pokemon(api, sid)
            pk.save_pokemon(conn, payload)  # Transaction par espece, RG10 et RG13.
            done += 1
            if done <= 3 or done % 25 == 0 or i == len(ids):
                print(f'  [{i}/{len(ids)}] #{sid} {payload["name"]} : OK', flush=True)
        except Exception as exc:
            # Une erreur propre a une espece n'arrete pas toutes les generations.
            errors.append(f'Pokemon #{sid}: {exc}')
            print(f'  [ERREUR] Pokemon #{sid}: {exc}', file=sys.stderr, flush=True)
    update_sequences(conn, [
        ('generation', 'id_generation'), ('type', 'id_type'),
        ('talent', 'id_talent'), ('pokemon', 'id_pokemon'),
    ])
    print(f'  RESULTAT Pokemon : {done} enregistres, {skipped} preserves, {len(errors)} erreurs.')
    return errors


def import_evolutions(conn, api, ids):
    print('\n[EVOLUTIONS] Exploration des chaines de toutes les generations...')
    # La fonction de parcours de l'ancien importeur excluait les numeros >151.
    # L'elargir aux especes reellement presentes permet de garder le meme
    # traitement des conditions ET / OU deja valide dans le schema.
    present = existing_ids(conn)
    ev.KANTO = frozenset(present)
    visited = set()
    edges = {}
    incompatible = set()
    errors = []
    for i, sid in enumerate(ids, 1):
        if sid not in present:
            continue
        try:
            species = api.get(f'pokemon-species/{sid}/')
            chain_ref = species.get('evolution_chain')
            if not chain_ref:
                continue
            chain_id = pk.resource_id(chain_ref)
            if chain_id in visited:
                continue
            visited.add(chain_id)
            chain = api.get(chain_ref['url'])
            for edge in ev.walk_chain(chain, chain_id):
                if edge.target in incompatible:
                    continue
                old = edges.get(edge.target)
                if old and old.source != edge.source:
                    errors.append(f'Cible #{edge.target}: deux origines #{old.source}/#{edge.source}; ignoree')
                    edges.pop(edge.target, None)
                    incompatible.add(edge.target)
                    continue
                if old:
                    edge = ev.Edge(edge.source, edge.target, chain_id,
                                   tuple(dict.fromkeys(old.conditions + edge.conditions)))
                edges[edge.target] = edge
            if len(visited) % 50 == 0:
                print(f'  {len(visited)} chaines parcourues / {i} especes examinees', flush=True)
        except Exception as exc:
            errors.append(f'Chaine espece #{sid}: {exc}')
            print(f'  [ERREUR] Chaine espece #{sid}: {exc}', file=sys.stderr)
    inserted = links = already = 0
    for edge in sorted(edges.values(), key=lambda e: e.target):
        try:
            created, added = ev.upsert_one(conn, edge)
            inserted += bool(created)
            links += added
            already += not created and added == 0
        except Exception as exc:
            errors.append(f'Evolution #{edge.source} -> #{edge.target}: {exc}')
            print(f'  [ERREUR] Evolution #{edge.source} -> #{edge.target}: {exc}', file=sys.stderr)
    update_sequences(conn, [('evolution', 'id_evolution'),
                            ('condition_evolution', 'id_condition')])
    print(f'  RESULTAT Evolutions : {inserted} ajoutees, {links} liens ajoutes, '
          f'{already} deja completes, {len(errors)} erreurs.')
    return errors


def import_method(conn, method_id, code, description, known, errors):
    if method_id in known:
        return True
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO methode_apprentissage
                      (id_methode, nom_methode, description_methode)
                    VALUES (%s, %s, %s) ON CONFLICT (id_methode) DO NOTHING
                ''', (method_id, code, description))
                cur.execute('SELECT nom_methode FROM methode_apprentissage WHERE id_methode=%s',
                            (method_id,))
                row = cur.fetchone()
                if not row or row[0] != code:
                    raise ValueError(f'Methode #{method_id}: conflit de nom {row}')
        known.add(method_id)
        return True
    except Exception as exc:
        errors.append(f'Methode {code} (#{method_id}): {exc}')
        return False


def import_all_moves(conn, api):
    """Inserer le catalogue complet, y compris les attaques non apprises."""
    print('\n[CAPACITES] Telechargement du catalogue de toutes les capacites...')
    entries = []
    page_url = 'move/?limit=200&offset=0'
    while page_url:
        page = api.get(page_url)
        entries.extend(page.get('results', []))
        page_url = page.get('next')
    errors = []
    added = 0
    with conn.cursor() as cur:
        cur.execute('SELECT id_capacite, nom_capacite FROM capacite')
        rows = cur.fetchall()
    known_ids = {r[0] for r in rows}
    used_names = {r[1]: r[0] for r in rows}
    for n, ref in enumerate(entries, 1):
        move_id = pk.resource_id(ref)
        if move_id in known_ids:
            continue
        try:
            obj = api.get(ref['url'])
            label = ca.normalize_text(ca.localized(obj.get('names', []), 'name')
                                      or obj['name'], 100)
            if not label:
                raise ValueError('Nom manquant')
            if label in used_names and used_names[label] != move_id:
                # Conserver les deux attaques quand le nom traduit est identique.
                suffix = f' [#{move_id}]'
                label = label[:100 - len(suffix)] + suffix
            category = ca.DAMAGE_CLASSES.get((obj.get('damage_class') or {}).get('name'))
            if category not in ('PHYSIQUE', 'SPECIALE', 'STATUT'):
                raise ValueError('Categorie inconnue')
            description = ca.normalize_text(
                ca.localized(obj.get('flavor_text_entries', []), 'flavor_text'), 500)
            power, accuracy, pp = obj.get('power'), obj.get('accuracy'), obj.get('pp')
            if power is not None and (not isinstance(power, int) or power < 0):
                raise ValueError(f'Puissance invalide {power}')
            if accuracy is not None and (not isinstance(accuracy, int) or accuracy < 0 or accuracy > 100):
                raise ValueError(f'Precision invalide {accuracy}')
            if accuracy == 0:
                accuracy = None  # Le schema refuse 0, pas d'invention de chance.
            if pp is not None and (not isinstance(pp, int) or pp < 0):
                raise ValueError(f'PP invalides {pp}')
            if pp == 0:
                pp = None
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO capacite (id_capacite, nom_capacite, description_capacite,
                                             categorie, puissance, precision_capacite, points_pouvoir)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id_capacite) DO NOTHING
                    ''', (move_id, label, description, category, power, accuracy, pp))
            known_ids.add(move_id)
            used_names[label] = move_id
            added += 1
            if added % 100 == 0 or n == len(entries):
                print(f'  Capacites : {n}/{len(entries)} examinees, {added} ajoutees', flush=True)
        except Exception as exc:
            errors.append(f'Capacite #{move_id}: {exc}')
            print(f'  [ERREUR] Capacite #{move_id}: {exc}', file=sys.stderr)
    update_sequences(conn, [('capacite', 'id_capacite')])
    print(f'  RESULTAT catalogue : {added} capacites ajoutees, {len(errors)} erreurs.')
    return known_ids, errors


def import_learnsets(conn, api, ids, version_group=None):
    print('\n[APPRENTISSAGES] Lecture des capacites par Pokemon...')
    known_moves, errors = import_all_moves(conn, api)
    with conn.cursor() as cur:
        cur.execute('SELECT id_methode FROM methode_apprentissage')
        known_methods = {r[0] for r in cur.fetchall()}
    present = existing_ids(conn)
    added = 0
    done = 0
    for sid in ids:
        if sid not in present:
            continue
        try:
            species = api.get(f'pokemon-species/{sid}/')
            default = next((item for item in species.get('varieties', [])
                            if item.get('is_default')), None)
            if default is None:
                raise ValueError('Aucune forme par defaut')
            obj = api.get(default['pokemon']['url'])
            # Notre MLD n'a pas de cle Version => reunion des versions.
            # Pour chaque triplet Pokemon/methode/capacite, un seul niveau
            # peut etre stocke. Selection : le niveau positif minimal.
            links = {}
            methods = {}
            for item in obj.get('moves') or []:
                move_id = pk.resource_id(item['move'])
                if move_id not in known_moves:
                    continue
                for d in item.get('version_group_details') or []:
                    if version_group and (d.get('version_group') or {}).get('name') != version_group:
                        continue
                    method_id, code, description, level = ca.method_for(d)
                    methods[method_id] = (code, description)
                    key = (sid, method_id, move_id)
                    if key not in links:
                        links[key] = level
                    elif level is not None and (links[key] is None or level < links[key]):
                        links[key] = level
            for method_id, (code, description) in methods.items():
                if not import_method(conn, method_id, code, description, known_methods, errors):
                    continue
            rows = [(*key, level) for key, level in links.items()
                    if key[1] in known_methods]
            if rows:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.executemany('''
                            INSERT INTO apprendre_capacite
                               (id_pokemon,id_methode,id_capacite,niveau_apprentissage)
                            VALUES (%s,%s,%s,%s)
                            ON CONFLICT (id_pokemon,id_methode,id_capacite) DO NOTHING
                        ''', rows)
                        added += max(cur.rowcount, 0)
            done += 1
            if done % 25 == 0 or done == len(ids):
                print(f'  Pokemon : {done}/{len(ids)} | nouvelles associations : {added}', flush=True)
        except Exception as exc:
            errors.append(f'Apprentissage Pokemon #{sid}: {exc}')
            print(f'  [ERREUR] Apprentissage Pokemon #{sid}: {exc}', file=sys.stderr)
    update_sequences(conn, [('methode_apprentissage', 'id_methode')])
    print(f'  RESULTAT apprentissages : {done} Pokemon traites, {added} liens ajoutes, '
          f'{len(errors)} erreurs.')
    return errors


def enrich_types(conn, api):
    """Remplir seulement les descriptions manquantes, avec donnees de type."""
    print('\n[TYPES] Completer les descriptions a partir des interactions PokéAPI...')
    errors = []
    with conn.cursor() as cur:
        cur.execute('SELECT id_type, nom_type FROM type')
        labels = dict(cur.fetchall())
    for tid, name in labels.items():
        try:
            obj = api.get(f'type/{tid}/')
            relations = obj.get('damage_relations') or {}
            parts = []
            for key, prefix in (('double_damage_to', 'Attaque x2 contre'),
                                ('double_damage_from', 'Subit x2 de')):
                references = [labels.get(pk.resource_id(x), x['name'])
                              for x in relations.get(key, [])]
                if references:
                    parts.append(prefix + ' : ' + ', '.join(references))
            desc = ' ; '.join(parts)[:255]
            if desc:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute('''
                            UPDATE type SET description_type = %s
                            WHERE id_type = %s AND (description_type IS NULL OR description_type = '')
                        ''', (desc, tid))
        except Exception as exc:
            errors.append(f'Type {name}: {exc}')
    print(f'  Descriptions de types traitees ; {len(errors)} erreur(s).')
    return errors


def list_regions(api):
    refs = []
    url = 'region/?limit=100'
    while url:
        page = api.get(url)
        refs.extend(page.get('results', []))
        url = page.get('next')
    return refs


def import_geography(conn, api, ids):
    print('\n[GEOGRAPHIE] Toutes les regions, lieux, habitats et rencontres PokéAPI...')
    errors = []
    present = existing_ids(conn)
    # Habitats attestes au niveau de l'ESPECE, pas des lieux.
    habitats = {}
    species_habitats = set()
    for i, sid in enumerate(ids, 1):
        if sid not in present:
            continue
        try:
            species = api.get(f'pokemon-species/{sid}/')
            habitat_ref = species.get('habitat')
            if not habitat_ref:
                continue  # PokéAPI ne precise pas l'habitat de toute espece.
            hid = pk.resource_id(habitat_ref)
            if hid not in habitats:
                detail = api.get(habitat_ref['url'])
                habitats[hid] = geo.name_fr(detail, 100, habitat_ref['name'])
            species_habitats.add((sid, hid))
        except Exception as exc:
            errors.append(f'Habitat Pokemon #{sid}: {exc}')
        if i % 250 == 0:
            print(f'  Especes/habitats : {i}/{len(ids)}', flush=True)
    regions_done = zones_count = locations_count = habitats_count = habitat_links = 0
    for rref in list_regions(api):
        try:
            region = api.get(rref['url'])
            rid = int(region['id'])
            region_label = geo.name_fr(region, 100, rref['name'])
            zones = {}
            encounters = set()
            areas_seen = set()
            location_refs = region.get('locations') or []
            print(f'  Region {region_label} : {len(location_refs)} lieux a consulter...', flush=True)
            for index, lref in enumerate(location_refs, 1):
                try:
                    loc = api.get(lref['url'])
                    loc_id = int(loc['id'])
                    zones[loc_id] = (geo.name_fr(loc, 100, lref['name']), rid)
                    for area_ref in loc.get('areas') or []:
                        if area_ref['url'] in areas_seen:
                            continue
                        areas_seen.add(area_ref['url'])
                        area = api.get(area_ref['url'])
                        for entry in area.get('pokemon_encounters') or []:
                            poke_ref = entry.get('pokemon')
                            if poke_ref is None:
                                continue
                            pid = pk.resource_id(poke_ref)
                            if pid not in present:
                                # Les variétés non standard ne sont pas des espèces.
                                continue
                            if entry.get('version_details'):
                                encounters.add((pid, loc_id))
                except Exception as exc:
                    errors.append(f'Lieu {lref["name"]}: {exc}')
                if index % 35 == 0 or index == len(location_refs):
                    print(f'    {index}/{len(location_refs)} lieux ; '
                          f'{len(encounters)} rencontres uniques', flush=True)
            dataset = geo.GeographicData(
                region=(rid, region_label),
                zones=zones,
                habitats=habitats,
                species_habitats=species_habitats,
                locations=encounters,
                areas_count=len(areas_seen),
                matching_entries=len(encounters),
                pokemon_without_habitat=[],
            )
            counts = geo.persist(conn, dataset)  # RG07 cree apparaitre_region.
            regions_done += counts[0]
            zones_count += counts[1]
            habitats_count += counts[2]
            habitat_links += counts[3]
            locations_count += counts[4]
            print(f'    => +{counts[1]} zones, +{counts[4]} localisations', flush=True)
        except Exception as exc:
            errors.append(f'Region {rref.get("name")}: {exc}')
            print(f'  [ERREUR] Region {rref.get("name")}: {exc}', file=sys.stderr)
    print(f'  RESULTAT geographie : +{regions_done} regions, +{zones_count} zones, '
          f'+{habitats_count} habitats, +{habitat_links} relations habitats, '
          f'+{locations_count} localisations ; {len(errors)} erreurs.')
    print('  ACCUEILLIR_HABITAT reste vide : PokéAPI ne fournit pas cette relation.')
    return errors


def summary(conn):
    targets = (
        'generation', 'pokemon', 'type', 'posseder_type', 'talent', 'avoir_talent',
        'evolution', 'condition_evolution', 'etre_possible_si',
        'capacite', 'methode_apprentissage', 'apprendre_capacite',
        'region', 'zone', 'habitat', 'vivre_habitat', 'se_trouver',
        'apparaitre_region', 'accueillir_habitat', 'dresseur', 'pokedex',
        'referencer_pokemon',
    )
    print('\n==== BILAN REEL DE LA BASE PostgreSQL ====')
    with conn.cursor() as cur:
        for table in targets:
            cur.execute(f'SELECT COUNT(*) FROM public.{table}')
            print(f'  {table:24s} {cur.fetchone()[0]:>8}')


def main():
    parser = argparse.ArgumentParser(description='Importer au maximum les donnees PokéAPI dans notre MCD existant.')
    parser.add_argument('--phase', choices=('pokemon', 'evolutions', 'capacites',
                                            'geographie', 'types', 'tout', 'bilan'),
                        default='pokemon', help='Phase a importer (defaut pokemon)')
    parser.add_argument('--refresh-existing', action='store_true',
                        help='Mettre a jour les Pokemon deja en base (sinon preserves)')
    parser.add_argument('--version-group', default=None,
                        help='Version-group pour les apprentissages (defaut : toutes versions fusionnees)')
    parser.add_argument('--refresh-api', action='store_true',
                        help='Ignorer les reponses PokeAPI deja mises en cache')
    args = parser.parse_args()
    print('POKEDEX - Extension PokéAPI toutes generations')
    print('Aucun DROP/ALTER de table. Dresseur TOMS et Pokédex personnels preserves.')
    print('Les formes alternatives ne sont PAS inserees comme especes supplementaires.')
    if args.phase in ('capacites', 'tout'):
        print('ATTENTION : notre MCD fusionne les apprentissages de differentes versions ; '
              'une seule valeur de niveau par Pokemon/methode/capacite.')
    conn = None
    errors = []
    try:
        conn = connection()
        api = pk.PokeAPI(refresh=args.refresh_api)
        ids = [] if args.phase in ('types', 'bilan') else available_species(api)
        if args.phase in ('pokemon', 'tout'):
            errors.extend(import_species(conn, api, ids, args.refresh_existing))
        if args.phase in ('evolutions', 'tout'):
            errors.extend(import_evolutions(conn, api, ids))
        if args.phase in ('capacites', 'tout'):
            errors.extend(import_learnsets(conn, api, ids, args.version_group))
        if args.phase in ('geographie', 'tout'):
            errors.extend(import_geography(conn, api, ids))
        if args.phase in ('types', 'tout'):
            errors.extend(enrich_types(conn, api))
        summary(conn)
        if errors:
            target = Path(__file__).resolve().parent / 'pokedex_import_global_erreurs.log'
            target.write_text('\n'.join(errors) + '\n', encoding='utf-8')
            print(f'\nTermine avec {len(errors)} avertissement(s)/erreur(s). Details : {target.name}')
            return 2
        print('\nSUCCES : toutes les phases demandees ont ete traitees sans erreur signalee.')
        return 0
    except KeyboardInterrupt:
        print('\nInterruption par utilisateur ; les transactions deja terminees restent conservees.')
        return 130
    except Exception as exc:
        print(f'\nARRET : {exc}', file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
