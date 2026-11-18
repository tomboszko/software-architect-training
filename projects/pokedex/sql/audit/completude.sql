-- =====================================================================
-- POKEDEX - AUDIT DE COMPLETUDE DES DONNEES (LECTURE SEULE)
-- Compatible PostgreSQL / structure Looping du projet de Monsieur Toms.
-- A executer dans pgAdmin sur la base pokedex_dev.
-- N'effectue AUCUN INSERT, UPDATE, DELETE ni changement de structure.
-- Executez les SELECT independamment pour retrouver chaque resultat.
-- =====================================================================

-- 1) ETAT DES ATTRIBUTS : VALEURS NULL OU TEXTES VIDES
-- Une valeur manquante dans un champ facultatif n'est pas forcement une erreur.
WITH mesures (table_source, champ, manquant) AS (
    SELECT 'GENERATION', 'date_introduction', date_introduction IS NULL
    FROM generation
    UNION ALL
    SELECT 'POKEMON', 'categorie_pokedex', NULLIF(BTRIM(categorie_pokedex), '') IS NULL
    FROM pokemon
    UNION ALL
    SELECT 'POKEMON', 'description_pokedex', NULLIF(BTRIM(description_pokedex), '') IS NULL
    FROM pokemon
    UNION ALL
    SELECT 'POKEMON', 'url_image', NULLIF(BTRIM(url_image), '') IS NULL
    FROM pokemon
    UNION ALL
    SELECT 'TYPE', 'description_type', NULLIF(BTRIM(description_type), '') IS NULL
    FROM type
    UNION ALL
    SELECT 'TALENT', 'description_talent', NULLIF(BTRIM(description_talent), '') IS NULL
    FROM talent
    UNION ALL
    SELECT 'CAPACITE', 'description_capacite', NULLIF(BTRIM(description_capacite), '') IS NULL
    FROM capacite
    UNION ALL
    SELECT 'CAPACITE', 'precision_capacite', precision_capacite IS NULL
    FROM capacite
    UNION ALL
    SELECT 'CAPACITE', 'puissance', puissance IS NULL
    FROM capacite
    UNION ALL
    SELECT 'CAPACITE', 'points_pouvoir', points_pouvoir IS NULL
    FROM capacite
    UNION ALL
    SELECT 'REGION', 'description_region', NULLIF(BTRIM(description_region), '') IS NULL
    FROM region
    UNION ALL
    SELECT 'ZONE', 'description_zone', NULLIF(BTRIM(description_zone), '') IS NULL
    FROM zone
    UNION ALL
    SELECT 'HABITAT', 'description_habitat', NULLIF(BTRIM(description_habitat), '') IS NULL
    FROM habitat
    UNION ALL
    SELECT 'EVOLUTION', 'commentaire_evolution', NULLIF(BTRIM(commentaire_evolution), '') IS NULL
    FROM evolution
    UNION ALL
    SELECT 'CONDITION_EVOLUTION', 'valeur_condition', NULLIF(BTRIM(valeur_condition), '') IS NULL
    FROM condition_evolution
    UNION ALL
    SELECT 'CONDITION_EVOLUTION', 'description_condition', NULLIF(BTRIM(description_condition), '') IS NULL
    FROM condition_evolution
    UNION ALL
    SELECT 'METHODE_APPRENTISSAGE', 'description_methode', NULLIF(BTRIM(description_methode), '') IS NULL
    FROM methode_apprentissage
    UNION ALL
    SELECT 'SE_TROUVER', 'frequence_rencontre', NULLIF(BTRIM(frequence_rencontre), '') IS NULL
    FROM se_trouver
    UNION ALL
    SELECT 'APPARAITRE_REGION', 'remarque_presence', NULLIF(BTRIM(remarque_presence), '') IS NULL
    FROM apparaitre_region
)
SELECT
    table_source,
    champ,
    COUNT(*) AS total_lignes,
    COUNT(*) FILTER (WHERE NOT manquant) AS renseignes,
    COUNT(*) FILTER (WHERE manquant) AS manquants,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT manquant) / NULLIF(COUNT(*), 0), 1)
        AS pourcentage_renseigne
FROM mesures
GROUP BY table_source, champ
ORDER BY manquants DESC, table_source, champ;


-- 2) POKEMON A COMPLETER : DESCRIPTIONS OU IMAGES (50 PREMIERS)
SELECT
    p.id_pokemon,
    p.nom_pokemon,
    CASE WHEN NULLIF(BTRIM(p.description_pokedex), '') IS NULL THEN 'MANQUANTE' ELSE 'OK' END
        AS description,
    CASE WHEN NULLIF(BTRIM(p.url_image), '') IS NULL THEN 'MANQUANTE' ELSE 'OK' END
        AS image
FROM pokemon AS p
WHERE NULLIF(BTRIM(p.description_pokedex), '') IS NULL
   OR NULLIF(BTRIM(p.url_image), '') IS NULL
ORDER BY p.id_pokemon
LIMIT 50;


-- 3) COUVERTURE DES FICHES POKEMON PAR GENERATION
SELECT
    g.numero_generation,
    g.nom_generation,
    COUNT(*) AS pokemon,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(p.description_pokedex), '') IS NULL)
        AS descriptions_manquantes,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(p.url_image), '') IS NULL)
        AS images_manquantes
FROM pokemon p
JOIN generation g ON g.id_generation = p.id_generation
GROUP BY g.numero_generation, g.nom_generation
ORDER BY g.numero_generation;


-- 4) COUVERTURE RELATIONNELLE (INFORMATIVE : PAS DES ERREURS)
SELECT
    COUNT(*) AS total_pokemon,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM vivre_habitat vh WHERE vh.id_pokemon = p.id_pokemon
        )
    ) AS pokemon_sans_habitat,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM se_trouver st WHERE st.id_pokemon = p.id_pokemon
        )
    ) AS pokemon_sans_localisation,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM apprendre_capacite ac WHERE ac.id_pokemon = p.id_pokemon
        )
    ) AS pokemon_sans_capacite,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM apparaitre_region ar WHERE ar.id_pokemon = p.id_pokemon
        )
    ) AS pokemon_sans_region
FROM pokemon AS p;
