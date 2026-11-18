CREATE TABLE GENERATION(
   id_generation SERIAL,
   numero_generation INTEGER NOT NULL,
   nom_generation VARCHAR(100) NOT NULL,
   date_introduction DATE,
   PRIMARY KEY(id_generation),
   UNIQUE(numero_generation)
);

CREATE TABLE POKEMON(
   id_pokemon SERIAL,
   nom_pokemon VARCHAR(100) NOT NULL,
   categorie_pokedex VARCHAR(100) NOT NULL,
   description_pokedex VARCHAR(1000),
   taille_m NUMERIC(6,2) NOT NULL CHECK (taille_m > 0),
   url_image VARCHAR(500),
   poids_kg NUMERIC(7,2) NOT NULL CHECK (poids_kg >= 0),
   pv_base INTEGER NOT NULL CHECK (pv_base > 0),
   attaque_base INTEGER NOT NULL CHECK (attaque_base> 0),
   defense_base INTEGER NOT NULL CHECK (defense_base > 0),
   attaque_speciale INTEGER NOT NULL CHECK (attaque_speciale> 0),
   vitesse_base INTEGER NOT NULL CHECK (vitesse_base > 0),
   defense_speciale INTEGER NOT NULL CHECK (defense_speciale > 0),
   id_generation INTEGER NOT NULL,
   PRIMARY KEY(id_pokemon),
   UNIQUE(nom_pokemon),
   FOREIGN KEY(id_generation) REFERENCES GENERATION(id_generation)
);

--Une evolution va d'un POKEMON source a un POKEMON cible.
CREATE TABLE EVOLUTION(
   id_evolution SERIAL,
   commentaire_evolution VARCHAR(500),
   id_pokemon_cible INTEGER NOT NULL,
   id_pokemon_source INTEGER NOT NULL,
   PRIMARY KEY(id_evolution),
   UNIQUE(id_pokemon_cible),
   FOREIGN KEY(id_pokemon_cible) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_pokemon_source) REFERENCES POKEMON(id_pokemon)
);

CREATE TABLE CONDITION_EVOLUTION(
   id_condition SERIAL,
   type_condition VARCHAR(100) NOT NULL CHECK (LENGTH(TRIM(type_condition)) > 0),
   valeur_condition VARCHAR(100) CHECK (
valeur_condition IS NULL
 OR LENGTH(TRIM(valeur_condition)) > 0
),
   description_condition VARCHAR(500),
   PRIMARY KEY(id_condition)
);

CREATE TABLE TYPE(
   id_type SERIAL,
   nom_type VARCHAR(50) NOT NULL,
   description_type VARCHAR(255),
   PRIMARY KEY(id_type),
   UNIQUE(nom_type)
);

CREATE TABLE TALENT(
   id_talent SERIAL,
   nom_talent VARCHAR(100) NOT NULL,
   description_talent VARCHAR(500),
   PRIMARY KEY(id_talent),
   UNIQUE(nom_talent)
);

CREATE TABLE CAPACITE(
   id_capacite SERIAL,
   nom_capacite VARCHAR(100) NOT NULL,
   description_capacite VARCHAR(500),
   categorie VARCHAR(50) NOT NULL CHECK (categorie IN ('PHYSIQUE', 'SPECIALE', 'STATUT')),
   precision_capacite INTEGER CHECK (precision_capacite BETWEEN 1 AND 100),
   puissance INTEGER CHECK (puissance >= 0),
   points_pouvoir INTEGER CHECK (points_pouvoir > 0),
   PRIMARY KEY(id_capacite),
   UNIQUE(nom_capacite)
);

CREATE TABLE REGION(
   id_region SERIAL,
   nom_region VARCHAR(100) NOT NULL,
   description_region VARCHAR(500),
   PRIMARY KEY(id_region),
   UNIQUE(nom_region)
);

CREATE TABLE ZONE(
   id_zone SERIAL,
   nom_zone VARCHAR(100) NOT NULL,
   description_zone VARCHAR(500),
   id_region INTEGER NOT NULL,
   PRIMARY KEY(id_zone),
   FOREIGN KEY(id_region) REFERENCES REGION(id_region)
);

CREATE TABLE HABITAT(
   id_habitat SERIAL,
   nom_habitat VARCHAR(100) NOT NULL,
   description_habitat VARCHAR(500),
   PRIMARY KEY(id_habitat)
);

CREATE TABLE DRESSEUR(
   id_dresseur SERIAL,
   pseudonyme VARCHAR(100) NOT NULL,
   date_inscription DATE,
   PRIMARY KEY(id_dresseur),
   UNIQUE(pseudonyme)
);

CREATE TABLE POKEDEX(
   id_pokedex SERIAL,
   nom_pokedex VARCHAR(100) NOT NULL,
   date_creation DATE,
   id_dresseur INTEGER NOT NULL,
   PRIMARY KEY(id_pokedex),
   FOREIGN KEY(id_dresseur) REFERENCES DRESSEUR(id_dresseur)
);

CREATE TABLE METHODE_APPRENTISSAGE(
   id_methode SERIAL,
   nom_methode VARCHAR(50) NOT NULL CHECK (LENGTH(TRIM(nom_methode)) > 0),
   description_methode VARCHAR(255),
   PRIMARY KEY(id_methode),
   UNIQUE(nom_methode)
);

CREATE TABLE ETRE_POSSIBLE_SI(
   id_evolution INTEGER,
   id_condition INTEGER,
   PRIMARY KEY(id_evolution, id_condition),
   FOREIGN KEY(id_evolution) REFERENCES EVOLUTION(id_evolution),
   FOREIGN KEY(id_condition) REFERENCES CONDITION_EVOLUTION(id_condition)
);

CREATE TABLE POSSEDER_TYPE(
   id_pokemon INTEGER,
   id_type INTEGER,
   position_type INTEGER NOT NULL CHECK (position_type IN (1, 2)),
   PRIMARY KEY(id_pokemon, id_type),
   UNIQUE(id_pokemon, position_type),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_type) REFERENCES TYPE(id_type)
);

CREATE TABLE AVOIR_TALENT(
   id_pokemon INTEGER,
   id_talent INTEGER,
   est_cache BOOLEAN NOT NULL,
   PRIMARY KEY(id_pokemon, id_talent),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_talent) REFERENCES TALENT(id_talent)
);

CREATE TABLE APPRENDRE_CAPACITE(
   id_pokemon INTEGER,
   id_methode INTEGER,
   id_capacite INTEGER,
   niveau_apprentissage INTEGER,
   PRIMARY KEY(id_pokemon, id_methode, id_capacite),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_methode) REFERENCES METHODE_APPRENTISSAGE(id_methode),
   FOREIGN KEY(id_capacite) REFERENCES CAPACITE(id_capacite)
);

CREATE TABLE SE_TROUVER(
   id_pokemon INTEGER,
   id_zone INTEGER,
   frequence_rencontre VARCHAR(50),
   PRIMARY KEY(id_pokemon, id_zone),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_zone) REFERENCES ZONE(id_zone)
);

CREATE TABLE VIVRE_HABITAT(
   id_pokemon INTEGER,
   id_habitat INTEGER,
   PRIMARY KEY(id_pokemon, id_habitat),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_habitat) REFERENCES HABITAT(id_habitat)
);

CREATE TABLE REFERENCER_POKEMON(
   id_pokedex INTEGER,
   id_pokemon INTEGER,
   statut_decouverte VARCHAR(10) NOT NULL CHECK (
    (statut_decouverte = 'VU'
     AND date_premiere_capture IS NULL)
    OR
    (statut_decouverte = 'CAPTURE'
     AND date_premiere_capture IS NOT NULL)
), --Valeurs autorisées : VU, CAPTURE
   date_premiere_vue DATE NOT NULL,
   date_premiere_capture DATE CHECK (date_premiere_capture IS NULL OR date_premiere_capture >= date_premiere_vue),
   PRIMARY KEY(id_pokedex, id_pokemon),
   FOREIGN KEY(id_pokedex) REFERENCES POKEDEX(id_pokedex),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon)
);

CREATE TABLE APPARAITRE_REGION(
   id_pokemon INTEGER,
   id_region INTEGER,
   remarque_presence VARCHAR(255),
   PRIMARY KEY(id_pokemon, id_region),
   FOREIGN KEY(id_pokemon) REFERENCES POKEMON(id_pokemon),
   FOREIGN KEY(id_region) REFERENCES REGION(id_region)
);

CREATE TABLE ACCUEILLIR_HABITAT(
   id_zone INTEGER,
   id_habitat INTEGER,
   PRIMARY KEY(id_zone, id_habitat),
   FOREIGN KEY(id_zone) REFERENCES ZONE(id_zone),
   FOREIGN KEY(id_habitat) REFERENCES HABITAT(id_habitat)
);

--RG04_Un Pokémon ne peut pas évoluer vers lui-même.
ALTER TABLE EVOLUTION ADD CONSTRAINT chk_evolution_distincte CHECK (id_pokemon_source <> id_pokemon_cible);

--La présence dans une zone implique la présence dans sa région.
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


--Lorsque la méthode d'apprentissage est NIVEAU, l'attribut niveau_apprentissage doit être renseigné.
CREATE OR REPLACE FUNCTION verifier_niveau_apprentissage() RETURNS TRIGGER LANGUAGE plpgsql AS $$ DECLARE v_methode TEXT; BEGIN SELECT nom_methode INTO v_methode FROM methode_apprentissage WHERE id_methode = NEW.id_methode FOR SHARE; IF UPPER(TRIM(v_methode)) = 'NIVEAU' AND (NEW.niveau_apprentissage IS NULL OR NEW.niveau_apprentissage < 1) THEN RAISE EXCEPTION 'RG09 : un apprentissage par niveau exige un niveau valide'; END IF; RETURN NEW; END; $$; CREATE OR REPLACE TRIGGER trg_rg09_apprentissage BEFORE INSERT OR UPDATE ON apprendre_capacite FOR EACH ROW EXECUTE FUNCTION verifier_niveau_apprentissage(); CREATE OR REPLACE FUNCTION rg09_verifier_renommage_methode() RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN IF UPPER(TRIM(NEW.nom_methode)) = 'NIVEAU' AND UPPER(TRIM(OLD.nom_methode)) IS DISTINCT FROM 'NIVEAU' THEN IF EXISTS ( SELECT 1 FROM apprendre_capacite WHERE id_methode = OLD.id_methode AND (niveau_apprentissage IS NULL OR niveau_apprentissage < 1) ) THEN RAISE EXCEPTION 'RG09 : impossible de renommer cette methode en NIVEAU'; END IF; END IF; RETURN NEW; END; $$; CREATE OR REPLACE TRIGGER trg_rg09_renommage BEFORE UPDATE OF nom_methode ON methode_apprentissage FOR EACH ROW EXECUTE FUNCTION rg09_verifier_renommage_methode();


--Chaque Pokémon doit posséder au moins un type. Il ne peut pas posséder plus de deux types distincts
CREATE OR REPLACE FUNCTION rg10_verifier_type_pokemon() RETURNS TRIGGER LANGUAGE plpgsql AS $$ DECLARE v_id INTEGER; BEGIN IF TG_TABLE_NAME = 'pokemon' THEN v_id := NEW.id_pokemon; ELSE v_id := OLD.id_pokemon; END IF; PERFORM 1 FROM pokemon WHERE id_pokemon = v_id FOR UPDATE; IF NOT FOUND THEN RETURN NULL; END IF; IF NOT EXISTS ( SELECT 1 FROM posseder_type WHERE id_pokemon = v_id ) THEN RAISE EXCEPTION 'RG10 : le Pokemon % doit posseder au moins un type', v_id; END IF; RETURN NULL; END; $$; CREATE CONSTRAINT TRIGGER trg_rg10_pokemon AFTER INSERT ON pokemon DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg10_verifier_type_pokemon(); CREATE CONSTRAINT TRIGGER trg_rg10_types AFTER DELETE OR UPDATE OF id_pokemon ON posseder_type DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg10_verifier_type_pokemon();


--Une évolution peut être associée à plusieurs conditions alternatives. La satisfaction d'au moins une de ces conditions suffit à permettre l'évolution. Les conditions associées à une même évolution ne sont donc pas cumulatives.
CREATE OR REPLACE FUNCTION rg12_verifier_conditions() RETURNS TRIGGER LANGUAGE plpgsql AS $$ DECLARE v_id INTEGER; BEGIN IF TG_TABLE_NAME = 'evolution' THEN v_id := NEW.id_evolution; ELSE v_id := OLD.id_evolution; END IF; PERFORM 1 FROM evolution WHERE id_evolution = v_id FOR UPDATE; IF NOT FOUND THEN RETURN NULL; END IF; IF NOT EXISTS ( SELECT 1 FROM etre_possible_si WHERE id_evolution = v_id ) THEN RAISE EXCEPTION 'RG12 : evolution % sans condition', v_id; END IF; RETURN NULL; END; $$; CREATE CONSTRAINT TRIGGER trg_rg12_evolution AFTER INSERT ON evolution DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg12_verifier_conditions(); CREATE CONSTRAINT TRIGGER trg_rg12_conditions AFTER DELETE OR UPDATE OF id_evolution ON etre_possible_si DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg12_verifier_conditions();


--Un Pokémon possède entre un et trois talents disponibles, dont au maximum un talent caché. Un même talent ne peut être associé deux fois au même Pokémon
CREATE UNIQUE INDEX ux_pokemon_talent_cache ON avoir_talent (id_pokemon) WHERE est_cache = TRUE; CREATE OR REPLACE FUNCTION rg13_verifier_talents() RETURNS TRIGGER LANGUAGE plpgsql AS $$ DECLARE v_ids INTEGER[]; v_id INTEGER; v_nombre INTEGER; v_caches INTEGER; BEGIN IF TG_TABLE_NAME = 'pokemon' THEN v_ids := ARRAY[NEW.id_pokemon]; ELSIF TG_OP = 'INSERT' THEN v_ids := ARRAY[NEW.id_pokemon]; ELSIF TG_OP = 'DELETE' THEN v_ids := ARRAY[OLD.id_pokemon]; ELSE v_ids := ARRAY[OLD.id_pokemon, NEW.id_pokemon]; END IF; FOR v_id IN SELECT DISTINCT id FROM unnest(v_ids) AS t(id) ORDER BY id LOOP PERFORM 1 FROM pokemon WHERE id_pokemon = v_id FOR UPDATE; IF NOT FOUND THEN CONTINUE; END IF; SELECT COUNT(*), COUNT(*) FILTER (WHERE est_cache = TRUE) INTO v_nombre, v_caches FROM avoir_talent WHERE id_pokemon = v_id; IF v_nombre < 1 OR v_nombre > 3 THEN RAISE EXCEPTION 'RG13 : Pokemon % doit posseder entre 1 et 3 talents', v_id; END IF; IF v_caches > 1 THEN RAISE EXCEPTION 'RG13 : Pokemon % possede plusieurs talents caches', v_id; END IF; END LOOP; RETURN NULL; END; $$; CREATE CONSTRAINT TRIGGER trg_rg13_pokemon AFTER INSERT ON pokemon DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg13_verifier_talents(); CREATE CONSTRAINT TRIGGER trg_rg13_talents AFTER INSERT OR UPDATE OR DELETE ON avoir_talent DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rg13_verifier_talents();

