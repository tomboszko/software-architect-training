-- Nouveau script de maintenance, non exécuté lors des validations historiques.
-- Lecture seule : les compteurs attendus sont zéro pour ces règles.
WITH types AS (
    SELECT p.id_pokemon, COUNT(pt.id_type) AS n
    FROM pokemon p LEFT JOIN posseder_type pt USING (id_pokemon)
    GROUP BY p.id_pokemon
), talents AS (
    SELECT p.id_pokemon, COUNT(at.id_talent) AS n,
           COUNT(*) FILTER (WHERE at.est_cache) AS caches
    FROM pokemon p LEFT JOIN avoir_talent at USING (id_pokemon)
    GROUP BY p.id_pokemon
)
SELECT 'RG10 : nombre de types invalide' AS controle, COUNT(*) AS anomalies
FROM types WHERE n NOT BETWEEN 1 AND 2
UNION ALL
SELECT 'RG13 : nombre de talents invalide', COUNT(*)
FROM talents WHERE n NOT BETWEEN 1 AND 3 OR caches > 1
UNION ALL
SELECT 'RG07 : presence regionale manquante', COUNT(*)
FROM se_trouver st JOIN zone z USING (id_zone)
WHERE NOT EXISTS (
    SELECT 1 FROM apparaitre_region ar
    WHERE ar.id_pokemon = st.id_pokemon AND ar.id_region = z.id_region
)
UNION ALL
SELECT 'RG12 : evolution sans condition', COUNT(*)
FROM evolution e WHERE NOT EXISTS (
    SELECT 1 FROM etre_possible_si c WHERE c.id_evolution = e.id_evolution
)
UNION ALL
SELECT 'RG04 : auto-evolution', COUNT(*)
FROM evolution WHERE id_pokemon_source = id_pokemon_cible
UNION ALL
SELECT 'RG09 : niveau invalide', COUNT(*)
FROM apprendre_capacite ac JOIN methode_apprentissage ma USING (id_methode)
WHERE UPPER(TRIM(ma.nom_methode)) = 'NIVEAU'
  AND (ac.niveau_apprentissage IS NULL OR ac.niveau_apprentissage < 1)
UNION ALL
SELECT 'RG06/RG11 : statut et dates incoherents', COUNT(*)
FROM referencer_pokemon
WHERE date_premiere_capture < date_premiere_vue
   OR NOT ((statut_decouverte = 'VU' AND date_premiere_capture IS NULL)
        OR (statut_decouverte = 'CAPTURE' AND date_premiere_capture IS NOT NULL));
