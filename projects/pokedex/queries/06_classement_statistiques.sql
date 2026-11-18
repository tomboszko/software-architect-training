-- Classement global par somme des six statistiques de base.
-- Lecture seule. RANK attribue le même rang aux ex aequo.

WITH statistiques AS (
    SELECT
        id_pokemon,
        nom_pokemon,
        pv_base,
        attaque_base,
        defense_base,
        attaque_speciale,
        defense_speciale,
        vitesse_base,
        (
            pv_base +
            attaque_base +
            defense_base +
            attaque_speciale +
            defense_speciale +
            vitesse_base
        ) AS total
    FROM pokemon
)
SELECT
    RANK() OVER (ORDER BY total DESC) AS classement,
    nom_pokemon,
    pv_base,
    attaque_base,
    defense_base,
    attaque_speciale,
    defense_speciale,
    vitesse_base,
    total
FROM statistiques
ORDER BY classement, nom_pokemon;
