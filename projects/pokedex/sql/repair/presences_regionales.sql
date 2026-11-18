-- Nouveau script de maintenance, non exécuté localement.
-- Corrige uniquement les présences régionales déductibles des zones (RG07).
-- Exécuter d'abord sql/audit/integrite.sql ; ne pas inventer de présence.
BEGIN;

DO $$
BEGIN
    IF current_database() <> 'pokedex_dev' THEN
        RAISE EXCEPTION 'Base incorrecte : %', current_database();
    END IF;
END;
$$;

WITH ajouts AS (
    INSERT INTO apparaitre_region (id_pokemon, id_region)
    SELECT DISTINCT st.id_pokemon, z.id_region
    FROM se_trouver st
    JOIN zone z USING (id_zone)
    ON CONFLICT (id_pokemon, id_region) DO NOTHING
    RETURNING id_pokemon, id_region
)
SELECT COUNT(*) AS presences_regionales_ajoutees FROM ajouts;

COMMIT;
-- Relancer l'audit après la transaction. Aucun autre lien n'est modifié.
