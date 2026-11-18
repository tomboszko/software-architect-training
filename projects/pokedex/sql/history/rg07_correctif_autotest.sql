-- POKEDEX / PostgreSQL 18 — RG07
-- Correctif autonome et reutilisable, sans suppression de donnees existantes.
-- Executez l'INTEGRALITE du fichier avec F5 dans pgAdmin sur pokedex_dev.
-- Ne selectionnez pas une partie du texte. Activez Auto commit dans pgAdmin.
-- Il n'y a volontairement aucun BEGIN/COMMIT/ROLLBACK manuel.
-- Les donnees de test sont annulees automatiquement par un bloc PL/pgSQL.

-- 1) Ajouter la presence regionale a chaque nouvelle localisation precise.
CREATE OR REPLACE FUNCTION public.rg07_sync_se_trouver()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
DECLARE
    v_id_region INTEGER;
BEGIN
    SELECT z.id_region INTO STRICT v_id_region
    FROM public.zone AS z
    WHERE z.id_zone = NEW.id_zone;

    INSERT INTO public.apparaitre_region (id_pokemon, id_region)
    VALUES (NEW.id_pokemon, v_id_region)
    ON CONFLICT (id_pokemon, id_region) DO NOTHING;

    RETURN NEW;
END;
$func$;

CREATE OR REPLACE TRIGGER trg_rg07_se_trouver
AFTER INSERT OR UPDATE OF id_pokemon, id_zone
ON public.se_trouver
FOR EACH ROW
EXECUTE FUNCTION public.rg07_sync_se_trouver();

-- 2) Enregistrer la nouvelle region si une zone change de region.
CREATE OR REPLACE FUNCTION public.rg07_sync_zone()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
BEGIN
    INSERT INTO public.apparaitre_region (id_pokemon, id_region)
    SELECT st.id_pokemon, NEW.id_region
    FROM public.se_trouver AS st
    WHERE st.id_zone = NEW.id_zone
    ON CONFLICT (id_pokemon, id_region) DO NOTHING;

    RETURN NEW;
END;
$func$;

CREATE OR REPLACE TRIGGER trg_rg07_zone
AFTER UPDATE OF id_region
ON public.zone
FOR EACH ROW
WHEN (OLD.id_region IS DISTINCT FROM NEW.id_region)
EXECUTE FUNCTION public.rg07_sync_zone();

-- 3) Interdire la suppression d'une presence regionale encore requise.
CREATE OR REPLACE FUNCTION public.rg07_proteger_presence_region()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.id_pokemon = OLD.id_pokemon
       AND NEW.id_region = OLD.id_region THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.se_trouver AS st
        JOIN public.zone AS z ON z.id_zone = st.id_zone
        WHERE st.id_pokemon = OLD.id_pokemon
          AND z.id_region = OLD.id_region
    ) THEN
        RAISE EXCEPTION
           'RG07 : presence regionale requise par une zone (Pokemon %, region %)',
           OLD.id_pokemon, OLD.id_region
           USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$func$;

CREATE OR REPLACE TRIGGER trg_rg07_presence_region
BEFORE DELETE OR UPDATE OF id_pokemon, id_region
ON public.apparaitre_region
FOR EACH ROW
EXECUTE FUNCTION public.rg07_proteger_presence_region();

-- 4) Regulariser les lignes deja presentes (operation additive, sans doublons).
INSERT INTO public.apparaitre_region (id_pokemon, id_region)
SELECT DISTINCT st.id_pokemon, z.id_region
FROM public.se_trouver AS st
JOIN public.zone AS z ON z.id_zone = st.id_zone
ON CONFLICT (id_pokemon, id_region) DO NOTHING;

-- 5) Verifier immediatement que les trois triggers sont actifs.
DO $verify$
DECLARE
    v_nb INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_nb
    FROM pg_trigger
    WHERE NOT tgisinternal
      AND tgenabled = 'O'
      AND (
          (tgname = 'trg_rg07_se_trouver' AND tgrelid = 'public.se_trouver'::regclass)
          OR (tgname = 'trg_rg07_zone' AND tgrelid = 'public.zone'::regclass)
          OR (tgname = 'trg_rg07_presence_region' AND tgrelid = 'public.apparaitre_region'::regclass)
      );

    IF v_nb <> 3 THEN
        RAISE EXCEPTION 'RG07 : installation incomplete (% triggers actifs sur 3)', v_nb;
    END IF;
    RAISE NOTICE 'PASS RG07-INSTALLATION : 3 triggers actifs';
END;
$verify$;

-- 6) Tests de comportement, sans conserver de donnees fictives.
-- Un bloc EXCEPTION PL/pgSQL annule les INSERT/UPDATE de son sous-bloc.
-- En cas d'echec inattendu, l'exception remonte et les modifications du test sont annulees.
DO $tests$
DECLARE
    v_generation INTEGER;
    v_pokemon INTEGER;
    v_region_a INTEGER;
    v_region_b INTEGER;
    v_region_c INTEGER;
    v_zone_a INTEGER;
    v_zone_b INTEGER;
    v_suffixe TEXT := pg_backend_pid()::TEXT || '_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSUS');
BEGIN
    BEGIN
        INSERT INTO public.generation (numero_generation, nom_generation)
        VALUES ((SELECT COALESCE(MAX(numero_generation), 0) + 1 FROM public.generation),
                'RG07_TEST_' || v_suffixe)
        RETURNING id_generation INTO v_generation;

        INSERT INTO public.pokemon (
            nom_pokemon, categorie_pokedex, taille_m, poids_kg,
            pv_base, attaque_base, defense_base,
            attaque_speciale, defense_speciale, vitesse_base, id_generation
        ) VALUES (
            'RG07_TEST_' || v_suffixe, 'Test', 1, 1,
            10, 10, 10, 10, 10, 10, v_generation
        ) RETURNING id_pokemon INTO v_pokemon;

        INSERT INTO public.region (nom_region)
        VALUES ('RG07_A_' || v_suffixe) RETURNING id_region INTO v_region_a;
        INSERT INTO public.region (nom_region)
        VALUES ('RG07_B_' || v_suffixe) RETURNING id_region INTO v_region_b;
        INSERT INTO public.region (nom_region)
        VALUES ('RG07_C_' || v_suffixe) RETURNING id_region INTO v_region_c;

        INSERT INTO public.zone (nom_zone, id_region)
        VALUES ('RG07_ZONE_A', v_region_a) RETURNING id_zone INTO v_zone_a;
        INSERT INTO public.zone (nom_zone, id_region)
        VALUES ('RG07_ZONE_B', v_region_b) RETURNING id_zone INTO v_zone_b;

        -- Test 1 : INSERT localisation => presence regionale automatique.
        INSERT INTO public.se_trouver (id_pokemon, id_zone)
        VALUES (v_pokemon, v_zone_a);
        IF NOT EXISTS (
            SELECT 1 FROM public.apparaitre_region
            WHERE id_pokemon = v_pokemon AND id_region = v_region_a
        ) THEN
            RAISE EXCEPTION 'ECHEC RG07-1 : presence regionale A absente';
        END IF;
        RAISE NOTICE 'PASS RG07-1 : presence regionale A creee';

        -- Test 2 : changer de zone => ajouter la nouvelle region.
        UPDATE public.se_trouver SET id_zone = v_zone_b
        WHERE id_pokemon = v_pokemon AND id_zone = v_zone_a;
        IF NOT EXISTS (
            SELECT 1 FROM public.apparaitre_region
            WHERE id_pokemon = v_pokemon AND id_region = v_region_b
        ) THEN
            RAISE EXCEPTION 'ECHEC RG07-2 : presence regionale B absente';
        END IF;
        RAISE NOTICE 'PASS RG07-2 : presence regionale B creee';

        -- Test 3 : une zone change de region => enregistrer C.
        UPDATE public.zone SET id_region = v_region_c WHERE id_zone = v_zone_b;
        IF NOT EXISTS (
            SELECT 1 FROM public.apparaitre_region
            WHERE id_pokemon = v_pokemon AND id_region = v_region_c
        ) THEN
            RAISE EXCEPTION 'ECHEC RG07-3 : presence regionale C absente';
        END IF;
        RAISE NOTICE 'PASS RG07-3 : presence regionale C creee';

        -- Test 4 : impossible de supprimer la presence C tant qu'une zone l'exige.
        BEGIN
            DELETE FROM public.apparaitre_region
            WHERE id_pokemon = v_pokemon AND id_region = v_region_c;
            RAISE EXCEPTION 'ECHEC RG07-4 : suppression interdite acceptee';
        EXCEPTION WHEN check_violation THEN
            RAISE NOTICE 'PASS RG07-4 : suppression interdite refusee';
        END;

        -- Cette exception CONTROLEE annule les donnees de test.
        RAISE EXCEPTION 'FIN_TEST_RG07' USING ERRCODE = 'ZX001';
    EXCEPTION WHEN SQLSTATE 'ZX001' THEN
        RAISE NOTICE 'PASS RG07-ROLLBACK : donnees de test annulees';
    END;
END;
$tests$;

-- 7) Confirmation visible dans Data Output.
SELECT tgname AS nom_trigger,
       tgrelid::regclass AS table_concernee,
       tgenabled AS actif
FROM pg_trigger
WHERE NOT tgisinternal AND tgname LIKE 'trg_rg07_%'
ORDER BY tgname;

-- Note : une ancienne presence regionale est conservee apres un deplacement
-- de zone. Elle peut avoir ete connue independamment de cette zone.
