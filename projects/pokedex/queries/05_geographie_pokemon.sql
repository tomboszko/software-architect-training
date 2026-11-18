-- Géographie : zones de rencontre et habitats.
-- Deux requêtes indépendantes, en lecture seule.
-- Modifier 'Pikachu' dans chaque WHERE.
-- Une absence de résultat signifie une absence d'association enregistrée,
-- pas nécessairement une absence de rencontre ou d'habitat dans les jeux.

-- 1. Zones de rencontre et régions correspondantes.
SELECT
    p.nom_pokemon,
    r.nom_region,
    z.nom_zone,
    st.frequence_rencontre,
    z.description_zone
FROM pokemon p
JOIN se_trouver st
    ON st.id_pokemon = p.id_pokemon
JOIN zone z
    ON z.id_zone = st.id_zone
JOIN region r
    ON r.id_region = z.id_region
WHERE p.nom_pokemon ILIKE 'Pikachu'
ORDER BY r.nom_region, z.nom_zone;

-- 2. Habitats indépendamment des zones de rencontre.
SELECT
    p.nom_pokemon,
    h.nom_habitat,
    h.description_habitat
FROM pokemon p
JOIN vivre_habitat vh
    ON vh.id_pokemon = p.id_pokemon
JOIN habitat h
    ON h.id_habitat = vh.id_habitat
WHERE p.nom_pokemon ILIKE 'Pikachu';
