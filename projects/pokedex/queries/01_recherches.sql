-- Requêtes de départ, en lecture seule. À exécuter localement.
-- 1. Les Pokémon dont la troisième lettre est r (sans distinction de casse).
SELECT id_pokemon, nom_pokemon
FROM pokemon
WHERE nom_pokemon ILIKE '__r%'
ORDER BY nom_pokemon;

-- 2. Concaténer le nom et la catégorie dans une seule colonne.
SELECT id_pokemon,
       CONCAT_WS(' - ', nom_pokemon, categorie_pokedex) AS fiche
FROM pokemon
ORDER BY id_pokemon;

-- 3. Consulter les fiches et le nom de leur génération.
SELECT p.id_pokemon, p.nom_pokemon, p.categorie_pokedex,
       g.numero_generation, g.nom_generation
FROM pokemon AS p
JOIN generation AS g ON g.id_generation = p.id_generation
ORDER BY p.id_pokemon;
