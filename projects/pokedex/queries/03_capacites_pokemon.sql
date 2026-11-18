-- Capacités détaillées d'un Pokémon et méthodes d'apprentissage.
-- Modifier 'Pikachu' dans WHERE. Lecture seule.
-- Une ligne par combinaison Pokémon, capacité et méthode.

SELECT
    p.nom_pokemon,
    c.nom_capacite,
    c.categorie,
    c.puissance,
    c.precision_capacite,
    c.points_pouvoir,
    m.nom_methode,
    ac.niveau_apprentissage,
    c.description_capacite
FROM pokemon p
JOIN apprendre_capacite ac
    ON ac.id_pokemon = p.id_pokemon
JOIN capacite c
    ON c.id_capacite = ac.id_capacite
JOIN methode_apprentissage m
    ON m.id_methode = ac.id_methode
WHERE p.nom_pokemon ILIKE 'Pikachu'
ORDER BY c.nom_capacite, m.nom_methode;
