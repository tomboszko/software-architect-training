-- Progression par Pokédex et dresseur.
-- Lecture seule. Le dénominateur est le catalogue complet de la base,
-- sans restriction par génération ou région.
-- Un Pokémon CAPTURE est également compté parmi les Pokémon vus.

SELECT
    d.pseudonyme,
    pd.nom_pokedex,
    (SELECT COUNT(*) FROM pokemon) AS total_pokemon,

    COUNT(rp.id_pokemon) FILTER (
        WHERE rp.statut_decouverte IN ('VU', 'CAPTURE')
    ) AS pokemon_vus,

    COUNT(rp.id_pokemon) FILTER (
        WHERE rp.statut_decouverte = 'CAPTURE'
    ) AS pokemon_captures,

    (SELECT COUNT(*) FROM pokemon)
        - COUNT(rp.id_pokemon) AS pokemon_non_decouverts,

    ROUND(
        100.0 * COUNT(rp.id_pokemon)
        / NULLIF((SELECT COUNT(*) FROM pokemon), 0),
        2
    ) AS progression_decouverte_pct,

    ROUND(
        100.0 * COUNT(rp.id_pokemon) FILTER (
            WHERE rp.statut_decouverte = 'CAPTURE'
        )
        / NULLIF((SELECT COUNT(*) FROM pokemon), 0),
        2
    ) AS progression_capture_pct
FROM dresseur d
JOIN pokedex pd
    ON pd.id_dresseur = d.id_dresseur
LEFT JOIN referencer_pokemon rp
    ON rp.id_pokedex = pd.id_pokedex
GROUP BY
    d.id_dresseur,
    d.pseudonyme,
    pd.id_pokedex,
    pd.nom_pokedex;
