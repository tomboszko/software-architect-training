# Bibliothèque de requêtes SQL — en construction

Ce dossier accueillera progressivement les requêtes écrites pendant le fil rouge.

Objectifs : SELECT et filtres, LIKE/ILIKE et concaténation, jointures, agrégations, sous-requêtes, CTE, requêtes sur les évolutions, données géographiques, fiches Pokémon, progression du dresseur.

Les premiers exemples sont des requêtes en lecture seule. Ils sont à exécuter et documenter sur la base locale avant de les considérer comme validés.

| Fichier | Objet |
| --- | --- |
| [01_recherches.sql](01_recherches.sql) | Recherche et présentation des noms |
| [02_fiche_pokemon.sql](02_fiche_pokemon.sql) | Fiche verticale : 21 informations, statistiques, types, talents, habitats, régions, nombre de capacités et chaînes d'évolution ramifiées |
| [03_capacites_pokemon.sql](03_capacites_pokemon.sql) | Capacités détaillées et méthodes d'apprentissage |
| [04_conditions_evolution.sql](04_conditions_evolution.sql) | Famille évolutive et conditions de chaque évolution |
| [05_geographie_pokemon.sql](05_geographie_pokemon.sql) | Zones de rencontre, régions des zones et habitats |
| [06_classement_statistiques.sql](06_classement_statistiques.sql) | Classement global selon le total des statistiques |
| [07_progression_pokedex.sql](07_progression_pokedex.sql) | Progression des dresseurs : découvertes et captures |

Pour chaque future requête, indiquer l'objectif, les tables, les paramètres, un exemple de résultat observé et les limites. Les requêtes validées pourront ensuite guider la conception de l'API.

## 02 — Fiche Pokémon

Dans pgAdmin, exécuter le script sur la base `pokedex_dev`. Remplacer `'Pikachu'` dans la clause `WHERE p.nom_pokemon ILIKE 'Pikachu'` par le nom souhaité.

- `CROSS JOIN LATERAL` et `VALUES` produisent une ligne par information, avec les colonnes `information` et `valeur`.
- `STRING_AGG` rassemble les informations issues des associations et `COUNT(DISTINCT ...)` compte les capacités distinctes.
- `WITH RECURSIVE` remonte à la racine de la famille évolutive puis parcourt toutes les branches, avec protection contre les cycles via `UNION` et le tableau des identifiants visités.
- Exemple de chaîne attendue : `Pichu -> Pikachu -> Raichu`. Si plusieurs branches existent, chaque chemin complet occupe une ligne dans la cellule correspondante (selon le rendu du client SQL).

Le script conserve la requête de travail fournie, avec commentaires et indentation harmonisée. Il est en lecture seule ; les données facultatives absentes peuvent produire des valeurs NULL. L'identifiant affiché est celui de la table Pokémon, pas un numéro national garanti indépendamment de la méthode d'import. Les conditions d'évolution ne sont pas affichées. L'exécution sur la base locale n'a pas été vérifiée lors de cet ajout GitHub.

## 03 à 07 — Exploration du catalogue

| Script | Objectif pédagogique | Paramètre et limites |
| --- | --- | --- |
| 03 | Jointures sur une association ternaire | Remplacer `'Pikachu'` ; une ligne par capacité et méthode. |
| 04 | CTE récursive, parcours de graphe et CASE | Remplacer `'Pikachu'` ; conditions alternatives (OU) et données enregistrées uniquement. |
| 05 | Jointures géographiques | Remplacer le nom dans chacune des deux requêtes ; les zones et habitats manquants ne sont pas inventés. |
| 06 | CTE, calcul et fonction de fenêtrage RANK | Aucun paramètre ; les ex aequo partagent un rang. |
| 07 | LEFT JOIN, FILTER, GROUP BY, ROUND et NULLIF | Tous les Pokédex ; progression rapportée au catalogue entier. Un Pokémon capturé est aussi compté comme vu. |

Ces cinq scripts sont en lecture seule. Ils ont été ajoutés à partir des requêtes proposées pendant le fil rouge, avec des commentaires explicatifs. Leur exécution et leurs résultats sur la base locale restent à documenter ; aucune nouvelle validation PostgreSQL n'est revendiquée.
