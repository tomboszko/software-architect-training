-- POKEDEX / RG07 - fonctions et triggers pour Looping (PostgreSQL 18)
-- A placer dans la regle RG07, SQL APRES creation des tables.
-- N inclut ni donnees de test ni INSERT d initialisation.

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
