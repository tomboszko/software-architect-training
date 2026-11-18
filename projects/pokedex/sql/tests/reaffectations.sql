-- POKEDEX - Audit de robustesse : reaffectation d'associations
-- Compatible avec le dernier export PostgreSQL fourni par Looping.
-- Le script ne change pas le schema et termine par ROLLBACK.
-- A executer INTEGRALEMENT dans pgAdmin sur la base pokedex_dev.

BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';

DO $preflight$
BEGIN
    IF current_database() <> 'pokedex_dev' THEN
        RAISE EXCEPTION 'Base incorrecte : % (pokedex_dev attendue)', current_database();
    END IF;

    IF (SELECT COUNT(*)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND NOT t.tgisinternal
          AND t.tgname IN ('trg_rg10_pokemon', 'trg_rg10_types',
                           'trg_rg12_evolution', 'trg_rg12_conditions',
                           'trg_rg13_pokemon', 'trg_rg13_talents')) <> 6 THEN
        RAISE EXCEPTION 'Les six triggers RG10/RG12/RG13 attendus sont absents ou incomplets';
    END IF;

    RAISE NOTICE 'PASS preparation : bonne base, six triggers cibles presents';
END;
$preflight$;

-- Identifiants NEGATIFS et noms reserves a ce test.
-- Toute collision avec des donnees preexistantes stoppe le test sans effacement.
INSERT INTO generation (id_generation, numero_generation, nom_generation)
VALUES (-87001, 87001, 'AUDIT ROBUSTESSE GENERATION');

INSERT INTO type (id_type, nom_type) VALUES
    (-87001, 'AUDIT ROBUSTESSE TYPE 1'),
    (-87002, 'AUDIT ROBUSTESSE TYPE 2'),
    (-87003, 'AUDIT ROBUSTESSE TYPE 3');

INSERT INTO talent (id_talent, nom_talent) VALUES
    (-87001, 'AUDIT ROBUSTESSE TALENT 1'),
    (-87002, 'AUDIT ROBUSTESSE TALENT 2'),
    (-87003, 'AUDIT ROBUSTESSE TALENT 3');

INSERT INTO condition_evolution (id_condition, type_condition) VALUES
    (-87001, 'NIVEAU'),
    (-87002, 'PIERRE'),
    (-87003, 'ECHANGE');

INSERT INTO pokemon (
    id_pokemon, nom_pokemon, categorie_pokedex, taille_m, poids_kg,
    pv_base, attaque_base, defense_base, attaque_speciale,
    vitesse_base, defense_speciale, id_generation
) VALUES
    (-87001, 'AUDIT ROBUSTESSE P1', 'AUDIT', 1.00, 1.00, 10, 10, 10, 10, 10, 10, -87001),
    (-87002, 'AUDIT ROBUSTESSE P2', 'AUDIT', 1.00, 1.00, 10, 10, 10, 10, 10, 10, -87001),
    (-87003, 'AUDIT ROBUSTESSE P3', 'AUDIT', 1.00, 1.00, 10, 10, 10, 10, 10, 10, -87001);

INSERT INTO posseder_type (id_pokemon, id_type, position_type) VALUES
    (-87001, -87001, 1),
    (-87001, -87002, 2),
    (-87002, -87003, 1),
    (-87003, -87003, 1);

INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache) VALUES
    (-87001, -87001, FALSE),
    (-87001, -87002, FALSE),
    (-87002, -87003, FALSE),
    (-87003, -87003, FALSE);

INSERT INTO evolution (id_evolution, id_pokemon_source, id_pokemon_cible) VALUES
    (-87001, -87001, -87002),
    (-87002, -87002, -87003);

INSERT INTO etre_possible_si (id_evolution, id_condition) VALUES
    (-87001, -87001),
    (-87001, -87002),
    (-87002, -87003);

-- Force les controles differes sur les donnees de depart.
SET CONSTRAINTS ALL IMMEDIATE;

DO $audit$
DECLARE
    v_rejete BOOLEAN;
    v_erreur TEXT;
BEGIN
    RAISE NOTICE 'PASS initialisation : Pokemon, evolutions, types, talents et conditions coherents';

    -- RG10 : deplacer un type sans laisser le Pokemon source sans type.
    UPDATE posseder_type
    SET id_pokemon = -87002
    WHERE id_pokemon = -87001 AND id_type = -87002;

    IF (SELECT COUNT(*) FROM posseder_type WHERE id_pokemon = -87001) <> 1
       OR (SELECT COUNT(*) FROM posseder_type WHERE id_pokemon = -87002) <> 2 THEN
        RAISE EXCEPTION 'FAIL RG10 : deplacement valide non applique correctement';
    END IF;
    RAISE NOTICE 'PASS RG10 : reaffectation de type autorisee si les deux Pokemon restent valides';

    -- RG10 : retirer le dernier type via UPDATE (pas via DELETE).
    v_rejete := FALSE;
    BEGIN
        UPDATE posseder_type
        SET id_pokemon = -87003, position_type = 2
        WHERE id_pokemon = -87001 AND id_type = -87001;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_erreur = MESSAGE_TEXT;
        IF POSITION('RG10' IN v_erreur) > 0 THEN
            v_rejete := TRUE;
        ELSE
            RAISE;
        END IF;
    END;
    IF NOT v_rejete THEN
        RAISE EXCEPTION 'FAIL RG10 : reaffectation du dernier type acceptee';
    END IF;
    RAISE NOTICE 'PASS RG10 : reaffectation du dernier type refusee';

    -- RG13 : deplacer un talent sans depasser les bornes 1..3.
    UPDATE avoir_talent
    SET id_pokemon = -87002
    WHERE id_pokemon = -87001 AND id_talent = -87002;

    IF (SELECT COUNT(*) FROM avoir_talent WHERE id_pokemon = -87001) <> 1
       OR (SELECT COUNT(*) FROM avoir_talent WHERE id_pokemon = -87002) <> 2 THEN
        RAISE EXCEPTION 'FAIL RG13 : deplacement valide non applique correctement';
    END IF;
    RAISE NOTICE 'PASS RG13 : reaffectation d''un talent autorisee si les deux Pokemon restent valides';

    -- RG13 : retirer le dernier talent via UPDATE.
    v_rejete := FALSE;
    BEGIN
        UPDATE avoir_talent
        SET id_pokemon = -87003
        WHERE id_pokemon = -87001 AND id_talent = -87001;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_erreur = MESSAGE_TEXT;
        IF POSITION('RG13' IN v_erreur) > 0 THEN
            v_rejete := TRUE;
        ELSE
            RAISE;
        END IF;
    END;
    IF NOT v_rejete THEN
        RAISE EXCEPTION 'FAIL RG13 : reaffectation du dernier talent acceptee';
    END IF;
    RAISE NOTICE 'PASS RG13 : reaffectation du dernier talent refusee';

    -- RG12 : deplacer une condition sans laisser l'evolution source vide.
    UPDATE etre_possible_si
    SET id_evolution = -87002
    WHERE id_evolution = -87001 AND id_condition = -87002;

    IF (SELECT COUNT(*) FROM etre_possible_si WHERE id_evolution = -87001) <> 1
       OR (SELECT COUNT(*) FROM etre_possible_si WHERE id_evolution = -87002) <> 2 THEN
        RAISE EXCEPTION 'FAIL RG12 : deplacement valide non applique correctement';
    END IF;
    RAISE NOTICE 'PASS RG12 : reaffectation d''une condition autorisee';

    -- RG12 : retirer la derniere condition via UPDATE.
    v_rejete := FALSE;
    BEGIN
        UPDATE etre_possible_si
        SET id_evolution = -87002
        WHERE id_evolution = -87001 AND id_condition = -87001;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_erreur = MESSAGE_TEXT;
        IF POSITION('RG12' IN v_erreur) > 0 THEN
            v_rejete := TRUE;
        ELSE
            RAISE;
        END IF;
    END;
    IF NOT v_rejete THEN
        RAISE EXCEPTION 'FAIL RG12 : reaffectation de la derniere condition acceptee';
    END IF;
    RAISE NOTICE 'PASS RG12 : reaffectation de la derniere condition refusee';

    RAISE NOTICE 'SUCCES : tous les tests de reaffectation sont passes';
END;
$audit$;

-- Rien n'est conserve dans la base.
ROLLBACK;
