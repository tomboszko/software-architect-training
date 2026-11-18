-- Famille évolutive et conditions de chaque évolution.
-- Modifier 'Pikachu' dans le CTE famille. Lecture seule.
-- UNION élimine les identifiants déjà visités.
-- Plusieurs conditions d'une évolution représentent des alternatives (OU).

WITH RECURSIVE famille AS (
    SELECT id_pokemon
    FROM pokemon
    WHERE nom_pokemon ILIKE 'Pikachu'

    UNION

    SELECT
        CASE
            WHEN e.id_pokemon_source = f.id_pokemon
            THEN e.id_pokemon_cible
            ELSE e.id_pokemon_source
        END
    FROM famille f
    JOIN evolution e
        ON e.id_pokemon_source = f.id_pokemon
        OR e.id_pokemon_cible = f.id_pokemon
)
SELECT
    source.nom_pokemon || ' -> ' ||
    cible.nom_pokemon AS evolution,
    ce.type_condition,
    ce.valeur_condition,
    ce.description_condition,
    e.commentaire_evolution
FROM evolution e
JOIN pokemon source
    ON source.id_pokemon = e.id_pokemon_source
JOIN pokemon cible
    ON cible.id_pokemon = e.id_pokemon_cible
JOIN etre_possible_si eps
    ON eps.id_evolution = e.id_evolution
JOIN condition_evolution ce
    ON ce.id_condition = eps.id_condition
WHERE e.id_pokemon_source IN (
    SELECT id_pokemon FROM famille
)
ORDER BY source.nom_pokemon, cible.nom_pokemon;
