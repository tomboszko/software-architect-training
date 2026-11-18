-- ============================================================================
-- POKEDEX / ENRICHISSEMENT DOCUMENTE - 17 NOVEMBRE 2026
-- Base : pokedex_dev / PostgreSQL 18
-- ============================================================================
-- OBJECTIF
--   9 dates de premiere introduction des generations dans les jeux video.
--   11 descriptions courtes des regions, redactees et factuelles.
--    9 descriptions des categories d'habitat, redactees a partir des noms.
--
-- PROVENANCE
--   Dates : premiere sortie d'un jeu de la generation, en general au Japon.
--   Les dates NE sont PAS des informations fournies par PokeAPI.
--   Les descriptions ne sont PAS des citations officielles : elles ont ete
--   redigees pour ce Pokedex, sur la base des references ci-dessous.
--
--   https://corporate.pokemon.co.jp/en/aboutus/history/
--   https://bulbapedia.bulbagarden.net/wiki/List_of_games_by_release_date
--   https://press.pokemon.com/en/products/Pokemon-Sun-and-Pokemon-Moon
--   https://press.pokemon.com/en/POKEMON-SWORD-AND-POKEMON-SHIELD-AVAILABLE-NOW
--   https://press.pokemon.com/en/RELEASE-DATE-REVEALED-FOR-POKEMON-SCARLET-AND-POKEMON-VIOLET
--   https://bulbapedia.bulbagarden.net/wiki/Region
--   https://bulbapedia.bulbagarden.net/wiki/Orre
--   https://pokeapi.co/docs/v2 (endpoints region et pokemon-habitat)
--
-- GARANTIES
--   - Uniquement des UPDATE de champs NULL ou vides.
--   - Aucune modification des Pokemon, capacites, evolutions, relations,
--     dresseurs, Pokedex ou decouvertes personnelles.
--   - Aucun changement de schema.
--   - Transaction atomique ; relancable.
--   - Les 1013 descriptions de zone restent inchangees : PokéAPI ne contient
--     pas de champ de description narrative de ses lieux.
-- ============================================================================

BEGIN;

DO $verification$
BEGIN
    IF current_database() <> 'pokedex_dev' THEN
        RAISE EXCEPTION 'Base incorrecte : % (attendue : pokedex_dev)', current_database();
    END IF;

    IF (SELECT COUNT(*) FROM public.generation WHERE numero_generation BETWEEN 1 AND 9) <> 9 THEN
        RAISE EXCEPTION 'Les 9 generations attendues ne sont pas toutes presentes.';
    END IF;

    IF (SELECT COUNT(*) FROM public.region WHERE LOWER(BTRIM(nom_region)) IN
        ('kanto', 'johto', 'hoenn', 'sinnoh', 'unys', 'kalos',
         'alola', 'galar', 'paldea', 'hisui', 'orre')) <> 11 THEN
        RAISE EXCEPTION 'Les 11 regions attendues ne sont pas toutes presentes.';
    END IF;

    -- Les scripts d'import PokéAPI ont utilisé l'identifiant de l'API
    -- comme id_habitat. Refuser la mise a jour si ce prerequis n'est plus vrai.
    IF (SELECT COUNT(*) FROM public.habitat WHERE id_habitat BETWEEN 1 AND 9) <> 9 THEN
        RAISE EXCEPTION 'Les 9 identifiants habitat PokéAPI (1 a 9) sont absents.';
    END IF;

    RAISE NOTICE 'Precontrole OK : base, generations, regions, habitats.';
END;
$verification$;

DO $enrichissement$
DECLARE
    n INTEGER;
BEGIN
    -- ------------------------------------------------------------------------
    -- 1) GENERATION.date_introduction
    -- Regle de datation : premiere sortie du couple de jeux introduisant
    -- la generation (Japon, ou lancement mondial s'il est simultane).
    -- ------------------------------------------------------------------------
    UPDATE public.generation AS g
    SET date_introduction = d.date_sortie
    FROM (VALUES
        (1, DATE '1996-02-27'), -- Rouge / Vert, Japon
        (2, DATE '1999-11-21'), -- Or / Argent, Japon
        (3, DATE '2002-11-21'), -- Rubis / Saphir, Japon
        (4, DATE '2006-09-28'), -- Diamant / Perle, Japon
        (5, DATE '2010-09-18'), -- Noir / Blanc, Japon
        (6, DATE '2013-10-12'), -- X / Y, lancement simultane
        (7, DATE '2016-11-18'), -- Soleil / Lune, premier lancement
        (8, DATE '2019-11-15'), -- Epee / Bouclier, lancement mondial
        (9, DATE '2022-11-18')  -- Ecarlate / Violet, lancement mondial
    ) AS d(numero, date_sortie)
    WHERE g.numero_generation = d.numero
      AND g.date_introduction IS NULL;

    GET DIAGNOSTICS n = ROW_COUNT;
    RAISE NOTICE 'Dates de generation ajoutees : %', n;

    -- ------------------------------------------------------------------------
    -- 2) REGION.description_region
    -- Descriptions originales et synthetiques, non extraites telles quelles
    -- de PokeAPI. Le lien jeux-region est fonde sur les sources citees.
    -- ------------------------------------------------------------------------
    UPDATE public.region AS r
    SET description_region = d.texte
    FROM (VALUES
        ('kanto',  'Région des premiers jeux Pokémon Rouge et Vert (1996), où débute le Pokédex original.'),
        ('johto',  'Région introduite dans Pokémon Or et Argent (1999), liée à Kanto au cours de ces aventures.'),
        ('hoenn',  'Région de Pokémon Rubis et Saphir (2002), caractérisée par ses parcours terrestres et maritimes.'),
        ('sinnoh', 'Région de Pokémon Diamant et Perle (2006), correspondant à la région anciennement appelée Hisui.'),
        ('unys',   'Région introduite dans Pokémon Noir et Blanc (2010), inspirée de la région de New York.'),
        ('kalos',  'Région de Pokémon X et Y (2013), dont les paysages et la culture s’inspirent de la France.'),
        ('alola',  'Archipel de Pokémon Soleil et Lune (2016), inspiré des îles d’Hawaï.'),
        ('galar',  'Région de Pokémon Épée et Bouclier (2019), conçue à partir de références au Royaume-Uni.'),
        ('paldea', 'Région de Pokémon Écarlate et Violet (2022), inspirée de la péninsule Ibérique.'),
        ('hisui',  'Ancien nom de la région de Sinnoh, cadre de Légendes Pokémon : Arceus.'),
        ('orre',   'Région des jeux dérivés Pokémon Colosseum et Pokémon XD : Le Souffle des Ténèbres.')
    ) AS d(nom_cle, texte)
    WHERE LOWER(BTRIM(r.nom_region)) = d.nom_cle
      AND NULLIF(BTRIM(r.description_region), '') IS NULL;

    GET DIAGNOSTICS n = ROW_COUNT;
    RAISE NOTICE 'Descriptions de region ajoutees : %', n;

    -- ------------------------------------------------------------------------
    -- 3) HABITAT.description_habitat
    -- Les IDs 1 a 9 correspondent aux categories PokeAPI (cave, forest,
    -- grassland, mountain, rare, rough-terrain, sea, urban, waters-edge).
    -- Definitions redigees pour ce projet, et non textes officiels de l'API.
    -- ------------------------------------------------------------------------
    UPDATE public.habitat AS h
    SET description_habitat = d.texte
    FROM (VALUES
        (1, 'Grottes et cavités souterraines, habitat associé aux milieux rocheux fermés.'),
        (2, 'Forêts et espaces boisés.'),
        (3, 'Champs, prairies et espaces herbeux ouverts.'),
        (4, 'Montagnes et zones de relief élevé.'),
        (5, 'Catégorie « rares » : groupe de classification, sans milieu naturel unique.'),
        (6, 'Milieux hostiles et terrains difficiles ou accidentés.'),
        (7, 'Mers et étendues marines.'),
        (8, 'Environnements urbains et zones habitées.'),
        (9, 'Bords de l’eau, marécages et autres milieux humides.')
    ) AS d(id_api, texte)
    WHERE h.id_habitat = d.id_api
      AND NULLIF(BTRIM(h.description_habitat), '') IS NULL;

    GET DIAGNOSTICS n = ROW_COUNT;
    RAISE NOTICE 'Descriptions d habitat ajoutees : %', n;
END;
$enrichissement$;

COMMIT;

-- ============================================================================
-- BILAN - Lecture seule
-- ============================================================================
SELECT
    'GENERATION' AS table_source,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE date_introduction IS NOT NULL) AS renseignes
FROM public.generation
UNION ALL
SELECT
    'REGION', COUNT(*),
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(description_region), '') IS NOT NULL)
FROM public.region
UNION ALL
SELECT
    'HABITAT', COUNT(*),
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(description_habitat), '') IS NOT NULL)
FROM public.habitat
UNION ALL
SELECT
    'ZONE', COUNT(*),
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(description_zone), '') IS NOT NULL)
FROM public.zone;

-- Pour lire les dates :
-- SELECT numero_generation, nom_generation, date_introduction
-- FROM generation ORDER BY numero_generation;
