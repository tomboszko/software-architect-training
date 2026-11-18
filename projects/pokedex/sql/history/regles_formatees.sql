-- ============================================================================
-- POKEDEX | REGLES DE GESTION SQL (APRES CREATION DES TABLES)
-- RG09 : Apprentissage par niveau
-- RG10 : Au moins un type par Pokemon
-- RG12 : Au moins une condition par evolution
-- RG13 : Entre un et trois talents par Pokemon, dont au plus un cache
-- ============================================================================

-- ============================================================================
-- RG09 - APPRENTISSAGE
-- Lorsque la methode est NIVEAU, niveau_apprentissage doit etre renseigne.
-- ============================================================================

CREATE OR REPLACE FUNCTION verifier_niveau_apprentissage()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_methode TEXT;
BEGIN
    SELECT nom_methode
    INTO v_methode
    FROM methode_apprentissage
    WHERE id_methode = NEW.id_methode
    FOR SHARE;

    IF UPPER(TRIM(v_methode)) = 'NIVEAU'
       AND (
           NEW.niveau_apprentissage IS NULL
           OR NEW.niveau_apprentissage < 1
       )
    THEN
        RAISE EXCEPTION
            'RG09 : un apprentissage par niveau exige un niveau valide';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_rg09_apprentissage
BEFORE INSERT OR UPDATE
ON apprendre_capacite
FOR EACH ROW
EXECUTE FUNCTION verifier_niveau_apprentissage();

-- Empeche de renommer une methode en NIVEAU si ses apprentissages sont invalides.

CREATE OR REPLACE FUNCTION rg09_verifier_renommage_methode()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF UPPER(TRIM(NEW.nom_methode)) = 'NIVEAU'
       AND UPPER(TRIM(OLD.nom_methode)) IS DISTINCT FROM 'NIVEAU'
    THEN
        IF EXISTS (
            SELECT 1
            FROM apprendre_capacite
            WHERE id_methode = OLD.id_methode
              AND (
                  niveau_apprentissage IS NULL
                  OR niveau_apprentissage < 1
              )
        )
        THEN
            RAISE EXCEPTION
                'RG09 : impossible de renommer cette methode en NIVEAU';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_rg09_renommage
BEFORE UPDATE OF nom_methode
ON methode_apprentissage
FOR EACH ROW
EXECUTE FUNCTION rg09_verifier_renommage_methode();


-- ============================================================================
-- RG10 - TYPES OBLIGATOIRES
-- Chaque Pokemon doit posseder au moins un type et au plus deux types.
-- Le maximum est garanti par les contraintes sur POSSEDER_TYPE.
-- ============================================================================

CREATE OR REPLACE FUNCTION rg10_verifier_type_pokemon()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'pokemon' THEN
        v_id := NEW.id_pokemon;
    ELSE
        v_id := OLD.id_pokemon;
    END IF;

    PERFORM 1
    FROM pokemon
    WHERE id_pokemon = v_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM posseder_type
        WHERE id_pokemon = v_id
    )
    THEN
        RAISE EXCEPTION
            'RG10 : le Pokemon % doit posseder au moins un type', v_id;
    END IF;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_rg10_pokemon
AFTER INSERT
ON pokemon
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg10_verifier_type_pokemon();

CREATE CONSTRAINT TRIGGER trg_rg10_types
AFTER DELETE OR UPDATE OF id_pokemon
ON posseder_type
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg10_verifier_type_pokemon();


-- ============================================================================
-- RG12 - CONDITIONS D'EVOLUTION
-- Les conditions d'une evolution sont alternatives (OU).
-- Chaque evolution doit disposer d'au moins une condition possible.
-- ============================================================================

CREATE OR REPLACE FUNCTION rg12_verifier_conditions()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'evolution' THEN
        v_id := NEW.id_evolution;
    ELSE
        v_id := OLD.id_evolution;
    END IF;

    PERFORM 1
    FROM evolution
    WHERE id_evolution = v_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM etre_possible_si
        WHERE id_evolution = v_id
    )
    THEN
        RAISE EXCEPTION
            'RG12 : evolution % sans condition', v_id;
    END IF;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_rg12_evolution
AFTER INSERT
ON evolution
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg12_verifier_conditions();

CREATE CONSTRAINT TRIGGER trg_rg12_conditions
AFTER DELETE OR UPDATE OF id_evolution
ON etre_possible_si
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg12_verifier_conditions();


-- ============================================================================
-- RG13 - TALENTS
-- Chaque Pokemon possede entre un et trois talents, dont au plus un cache.
-- La cle primaire empeche d'attribuer deux fois le meme talent.
-- ============================================================================

CREATE UNIQUE INDEX ux_pokemon_talent_cache
ON avoir_talent (id_pokemon)
WHERE est_cache = TRUE;

CREATE OR REPLACE FUNCTION rg13_verifier_talents()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_ids INTEGER[];
    v_id INTEGER;
    v_nombre INTEGER;
    v_caches INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'pokemon' THEN
        v_ids := ARRAY[NEW.id_pokemon];
    ELSIF TG_OP = 'INSERT' THEN
        v_ids := ARRAY[NEW.id_pokemon];
    ELSIF TG_OP = 'DELETE' THEN
        v_ids := ARRAY[OLD.id_pokemon];
    ELSE
        v_ids := ARRAY[OLD.id_pokemon, NEW.id_pokemon];
    END IF;

    FOR v_id IN
        SELECT DISTINCT id
        FROM unnest(v_ids) AS t(id)
        ORDER BY id
    LOOP
        PERFORM 1
        FROM pokemon
        WHERE id_pokemon = v_id
        FOR UPDATE;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE est_cache = TRUE)
        INTO v_nombre, v_caches
        FROM avoir_talent
        WHERE id_pokemon = v_id;

        IF v_nombre < 1 OR v_nombre > 3 THEN
            RAISE EXCEPTION
                'RG13 : Pokemon % doit posseder entre 1 et 3 talents', v_id;
        END IF;

        IF v_caches > 1 THEN
            RAISE EXCEPTION
                'RG13 : Pokemon % possede plusieurs talents caches', v_id;
        END IF;
    END LOOP;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_rg13_pokemon
AFTER INSERT
ON pokemon
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg13_verifier_talents();

CREATE CONSTRAINT TRIGGER trg_rg13_talents
AFTER INSERT OR UPDATE OR DELETE
ON avoir_talent
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION rg13_verifier_talents();
