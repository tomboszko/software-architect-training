-- POKEDEX : tests fonctionnels RG04, RG07, RG09, RG10, RG11, RG12 et RG13
-- Base cible : pokedex_dev
-- EXECUTION : coller le script COMPLET dans pgAdmin Query Tool.
-- Les messages PASS/ECHEC apparaissent dans l'onglet Messages.
-- Aucun enregistrement de test n'est conserve : ROLLBACK final.
-- Les identifiants de test sont negatifs : aucune sequence SERIAL n'est consommee.

BEGIN;

DO $tests$
BEGIN
    IF current_database() <> 'pokedex_dev' THEN
        RAISE EXCEPTION 'TESTS BLOQUES : base active %, base attendue pokedex_dev', current_database();
    END IF;

    -- DONNEES MINIMALES COHERENTES
    INSERT INTO generation (id_generation, numero_generation, nom_generation)
    VALUES (-9001, 9999, 'TEST_RG_GENERATION');

    INSERT INTO type (id_type, nom_type) VALUES
        (-9001, 'TEST_RG_TYPE_1'),
        (-9002, 'TEST_RG_TYPE_2'),
        (-9003, 'TEST_RG_TYPE_3');

    INSERT INTO talent (id_talent, nom_talent) VALUES
        (-9001, 'TEST_RG_TALENT_1'),
        (-9002, 'TEST_RG_TALENT_2'),
        (-9003, 'TEST_RG_TALENT_3'),
        (-9004, 'TEST_RG_TALENT_4');

    INSERT INTO condition_evolution (id_condition, type_condition, valeur_condition)
    VALUES (-9001, 'NIVEAU', '20');

    INSERT INTO region (id_region, nom_region) VALUES
        (-9001, 'TEST_RG_REGION_1'),
        (-9002, 'TEST_RG_REGION_2');

    INSERT INTO zone (id_zone, nom_zone, id_region)
    VALUES (-9001, 'TEST_RG_ZONE_1', -9001);

    INSERT INTO methode_apprentissage (id_methode, nom_methode) VALUES
        (-9001, 'NIVEAU'),
        (-9002, 'TEST_RG_CT');

    INSERT INTO capacite (id_capacite, nom_capacite, categorie)
    VALUES (-9001, 'TEST_RG_CAPACITE', 'PHYSIQUE');

    INSERT INTO dresseur (id_dresseur, pseudonyme)
    VALUES (-9001, 'TEST_RG_DRESSEUR');

    INSERT INTO pokedex (id_pokedex, nom_pokedex, id_dresseur)
    VALUES (-9001, 'TEST_RG_POKEDEX', -9001);

    INSERT INTO pokemon (
        id_pokemon, nom_pokemon, categorie_pokedex, taille_m, poids_kg,
        pv_base, attaque_base, defense_base, attaque_speciale,
        defense_speciale, vitesse_base, id_generation
    ) VALUES
        (-9001, 'TEST_RG_POKEMON_A', 'TEST', 1.00, 10.00, 50, 50, 50, 50, 50, 50, -9001),
        (-9002, 'TEST_RG_POKEMON_B', 'TEST', 1.00, 10.00, 50, 50, 50, 50, 50, 50, -9001);

    INSERT INTO posseder_type (id_pokemon, id_type, position_type) VALUES
        (-9001, -9001, 1),
        (-9002, -9001, 1);

    INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache) VALUES
        (-9001, -9001, FALSE),
        (-9002, -9001, FALSE);

    INSERT INTO apprendre_capacite (id_pokemon, id_methode, id_capacite, niveau_apprentissage)
    VALUES
        (-9001, -9001, -9001, 10),
        (-9002, -9002, -9001, NULL);

    INSERT INTO evolution (id_evolution, id_pokemon_source, id_pokemon_cible)
    VALUES (-9001, -9001, -9002);

    INSERT INTO etre_possible_si (id_evolution, id_condition)
    VALUES (-9001, -9001);

    INSERT INTO referencer_pokemon (
        id_pokedex, id_pokemon, statut_decouverte, date_premiere_vue, date_premiere_capture
    ) VALUES (-9001, -9001, 'VU', DATE '2026-01-10', NULL);

    INSERT INTO se_trouver (id_pokemon, id_zone)
    VALUES (-9001, -9001);

    -- Force la verification des triggers differes MAINTENANT, sans COMMIT.
    SET CONSTRAINTS ALL IMMEDIATE;

    IF NOT EXISTS (
        SELECT 1 FROM apparaitre_region
        WHERE id_pokemon = -9001 AND id_region = -9001
    ) THEN
        RAISE EXCEPTION 'ECHEC RG07 : insertion regionale automatique absente';
    END IF;
    RAISE NOTICE 'PASS : insertion coherente (RG07/RG09/RG10/RG12/RG13)';
    RAISE NOTICE 'PASS RG07 : creation automatique de la presence regionale';

    SET CONSTRAINTS ALL DEFERRED;

    -- RG04 : l'evolution vers soi-meme doit etre refusee.
    BEGIN
        INSERT INTO evolution (id_evolution, id_pokemon_source, id_pokemon_cible)
        VALUES (-9002, -9001, -9001);
        RAISE EXCEPTION 'ECHEC RG04 : auto-evolution acceptee';
    EXCEPTION
        WHEN check_violation THEN RAISE NOTICE 'PASS RG04 : auto-evolution refusee';
        WHEN OTHERS THEN RAISE;
    END;

    -- RG07 : impossible d'effacer une region toujours exigee par une zone.
    BEGIN
        DELETE FROM apparaitre_region
        WHERE id_pokemon = -9001 AND id_region = -9001;
        RAISE EXCEPTION 'ECHEC RG07 : presence regionale requise supprimee';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG07 :%' THEN
            RAISE NOTICE 'PASS RG07 : suppression de presence requise refusee';
        ELSE RAISE;
        END IF;
    END;

    -- RG07 : deplacer une zone doit creer la presence dans la nouvelle region.
    UPDATE zone SET id_region = -9002 WHERE id_zone = -9001;
    IF NOT EXISTS (
        SELECT 1 FROM apparaitre_region
        WHERE id_pokemon = -9001 AND id_region = -9002
    ) THEN
        RAISE EXCEPTION 'ECHEC RG07 : changement de region non repercute';
    END IF;
    RAISE NOTICE 'PASS RG07 : changement de region de la zone repercute';

    -- RG09 : un apprentissage par niveau sans niveau doit etre refuse.
    BEGIN
        INSERT INTO apprendre_capacite
            (id_pokemon, id_methode, id_capacite, niveau_apprentissage)
        VALUES (-9002, -9001, -9001, NULL);
        RAISE EXCEPTION 'ECHEC RG09 : NIVEAU sans valeur accepte';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG09 :%' THEN
            RAISE NOTICE 'PASS RG09 : niveau NULL refuse';
        ELSE RAISE;
        END IF;
    END;

    -- RG09 : renommer une methode avec des apprentissages NULL en NIVEAU doit echouer.
    BEGIN
        UPDATE methode_apprentissage
        SET nom_methode = 'TEST_RG_NIVEAU_ANCIEN'
        WHERE id_methode = -9001;
        UPDATE methode_apprentissage
        SET nom_methode = 'NIVEAU'
        WHERE id_methode = -9002;
        RAISE EXCEPTION 'ECHEC RG09 : renommage incoherent accepte';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG09 :%' THEN
            RAISE NOTICE 'PASS RG09 : renommage incoherent refuse';
        ELSE RAISE;
        END IF;
    END;

    -- RG10 : creer un pokemon ayant un talent, mais aucun type.
    BEGIN
        INSERT INTO pokemon (
            id_pokemon, nom_pokemon, categorie_pokedex, taille_m, poids_kg,
            pv_base, attaque_base, defense_base, attaque_speciale,
            defense_speciale, vitesse_base, id_generation
        ) VALUES (-9003, 'TEST_RG_SANS_TYPE', 'TEST', 1, 10, 50, 50, 50, 50, 50, 50, -9001);
        INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache)
        VALUES (-9003, -9001, FALSE);
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG10 : pokemon sans type accepte';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG10 :%' THEN
            RAISE NOTICE 'PASS RG10 : pokemon sans type refuse';
        ELSE RAISE;
        END IF;
    END;

    -- RG10 : supprimer le dernier type d'un pokemon existant.
    BEGIN
        DELETE FROM posseder_type WHERE id_pokemon = -9001;
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG10 : suppression du dernier type acceptee';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG10 :%' THEN
            RAISE NOTICE 'PASS RG10 : suppression du dernier type refusee';
        ELSE RAISE;
        END IF;
    END;

    -- RG11 : statut CAPTURE sans date de capture.
    BEGIN
        INSERT INTO referencer_pokemon (
            id_pokedex, id_pokemon, statut_decouverte, date_premiere_vue, date_premiere_capture
        ) VALUES (-9001, -9002, 'CAPTURE', DATE '2026-01-10', NULL);
        RAISE EXCEPTION 'ECHEC RG11 : capture sans date acceptee';
    EXCEPTION
        WHEN check_violation THEN RAISE NOTICE 'PASS RG11 : capture sans date refusee';
        WHEN OTHERS THEN RAISE;
    END;

    -- RG11/RG06 : capture anterieure a la premiere vue.
    BEGIN
        INSERT INTO referencer_pokemon (
            id_pokedex, id_pokemon, statut_decouverte, date_premiere_vue, date_premiere_capture
        ) VALUES (-9001, -9002, 'CAPTURE', DATE '2026-01-10', DATE '2026-01-01');
        RAISE EXCEPTION 'ECHEC RG06 : date de capture anterieure acceptee';
    EXCEPTION
        WHEN check_violation THEN RAISE NOTICE 'PASS RG06 : capture anterieure a la vue refusee';
        WHEN OTHERS THEN RAISE;
    END;

    -- RG12 : une evolution sans condition doit etre refusee.
    BEGIN
        INSERT INTO evolution (id_evolution, id_pokemon_source, id_pokemon_cible)
        VALUES (-9002, -9002, -9001);
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG12 : evolution sans condition acceptee';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG12 :%' THEN
            RAISE NOTICE 'PASS RG12 : evolution sans condition refusee';
        ELSE RAISE;
        END IF;
    END;

    -- RG12 : impossible de supprimer la derniere condition.
    BEGIN
        DELETE FROM etre_possible_si WHERE id_evolution = -9001;
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG12 : suppression de la derniere condition acceptee';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG12 :%' THEN
            RAISE NOTICE 'PASS RG12 : suppression de la derniere condition refusee';
        ELSE RAISE;
        END IF;
    END;

    -- RG13 : un pokemon possedant un type, mais aucun talent, doit etre refuse.
    BEGIN
        INSERT INTO pokemon (
            id_pokemon, nom_pokemon, categorie_pokedex, taille_m, poids_kg,
            pv_base, attaque_base, defense_base, attaque_speciale,
            defense_speciale, vitesse_base, id_generation
        ) VALUES (-9004, 'TEST_RG_SANS_TALENT', 'TEST', 1, 10, 50, 50, 50, 50, 50, 50, -9001);
        INSERT INTO posseder_type (id_pokemon, id_type, position_type)
        VALUES (-9004, -9001, 1);
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG13 : pokemon sans talent accepte';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG13 :%' THEN
            RAISE NOTICE 'PASS RG13 : pokemon sans talent refuse';
        ELSE RAISE;
        END IF;
    END;

    -- RG13 : quatre talents (dont un deja present) doivent etre refuses.
    BEGIN
        INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache) VALUES
            (-9001, -9002, FALSE),
            (-9001, -9003, FALSE),
            (-9001, -9004, FALSE);
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG13 : quatre talents acceptes';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG13 :%' THEN
            RAISE NOTICE 'PASS RG13 : quatre talents refuses';
        ELSE RAISE;
        END IF;
    END;

    -- RG13 : l'index partiel interdit deux talents caches.
    BEGIN
        UPDATE avoir_talent SET est_cache = TRUE
        WHERE id_pokemon = -9001 AND id_talent = -9001;
        INSERT INTO avoir_talent (id_pokemon, id_talent, est_cache)
        VALUES (-9001, -9002, TRUE);
        RAISE EXCEPTION 'ECHEC RG13 : deux talents caches acceptes';
    EXCEPTION
        WHEN unique_violation THEN
            IF SQLERRM LIKE '%ux_pokemon_talent_cache%' THEN
                RAISE NOTICE 'PASS RG13 : deux talents caches refuses';
            ELSE RAISE;
            END IF;
        WHEN OTHERS THEN RAISE;
    END;

    -- RG13 : supprimer le dernier talent doit etre refuse.
    BEGIN
        DELETE FROM avoir_talent WHERE id_pokemon = -9001;
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'ECHEC RG13 : dernier talent supprime';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'RG13 :%' THEN
            RAISE NOTICE 'PASS RG13 : suppression du dernier talent refusee';
        ELSE RAISE;
        END IF;
    END;

    -- CHECK : categorie CAPACITE invalide.
    BEGIN
        INSERT INTO capacite (id_capacite, nom_capacite, categorie)
        VALUES (-9002, 'TEST_RG_CAPACITE_INVALIDE', 'MAGIE');
        RAISE EXCEPTION 'ECHEC CAPACITE : categorie MAGIE acceptee';
    EXCEPTION
        WHEN check_violation THEN RAISE NOTICE 'PASS CAPACITE : categorie invalide refusee';
        WHEN OTHERS THEN RAISE;
    END;

    RAISE NOTICE 'SUCCES : tous les tests executes ont donne le resultat attendu.';
END;
$tests$;

-- Annule TOUTES les insertions, modifications et suppressions de test.
ROLLBACK;
