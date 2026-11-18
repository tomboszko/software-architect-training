# Bilan du Pokédex — 17 novembre 2026

Résultats issus des compteurs retournés par PostgreSQL et des journaux d'exécution partagés lors du travail local. Ce n'est pas un export direct d'une base accessible depuis GitHub.

## Peuplement global observé

| Table | Lignes |
| --- | ---: |
| GENERATION | 9 |
| POKEMON | 1 025 |
| TYPE | 18 |
| POSSEDER_TYPE | 1 551 |
| TALENT | 284 |
| AVOIR_TALENT | 2 411 |
| EVOLUTION | 456 |
| CONDITION_EVOLUTION | 123 |
| ETRE_POSSIBLE_SI | 456 |
| CAPACITE | 937 |
| METHODE_APPRENTISSAGE | 12 |
| APPRENDRE_CAPACITE | 119 351 |
| REGION | 11 |
| ZONE | 1 013 |
| HABITAT | 9 |
| VIVRE_HABITAT | 386 |
| SE_TROUVER | 12 137 |
| APPARAITRE_REGION | 2 939 |
| ACCUEILLIR_HABITAT | 0 |
| DRESSEUR | 1 |
| POKEDEX | 1 |
| REFERENCER_POKEMON | 0 |

20 tables sur 22 renseignées. Les deux tables vides sont volontaires : aucune correspondance zone/habitat attestée n'a été trouvée, et aucune découverte personnelle n'a été injectée artificiellement.

## Validation et enrichissement

- Import initial Kanto : 151 espèces, puis 72 évolutions et 72 liens de conditions ; 163 capacités et 4 027 apprentissages, 96 lieux et 704 localisations.
- Export final : 18 vérifications fonctionnelles PASS (299 ms) ; 6 scénarios de réaffectation PASS (159 ms), ROLLBACK à la fin.
- Après extension : 1 025 Pokémon avec description, image (URL renseignée) et au moins une capacité.
- Habitats : 386 espèces renseignées, 639 sans habitat (générations 4 à 9).
- Localisations : 846 espèces renseignées, 179 sans localisation ni présence régionale. Hisui (89 zones) et Paldea (84 zones) sans rencontres importées.
- Descriptions de capacités : 18 des 23 textes manquants récupérés, soit 932/937 renseignées. 5 restent absentes de la source exploitée.
- Enrichissement documenté : 9 dates de génération, 11 descriptions de régions et 9 descriptions d'habitats ajoutées.
- Descriptions de zones : 722/1 013 produites à partir des sous-zones et associations existantes ; 291 restent vides, aucune erreur API signalée lors de cette exécution.

Une URL d'image renseignée ne prouve pas sa disponibilité permanente. Une association minimale ne prouve pas l'exhaustivité des données.

## Limites et décisions assumées

- Une fiche par espèce, pas par forme : les variantes régionales et autres formes alternatives ne sont pas représentées séparément.
- Les données biologiques sont issues des fiches actuelles de l'API. Les apprentissages et rencontres multi-éditions ne conservent pas la version de jeu. Les premières données de Kanto comportaient aussi des choix de versions spécifiques ; il ne faut pas interpréter l'ensemble comme un unique jeu historique.
- La clé primaire de l'association d'apprentissage implique un niveau représentatif par combinaison Pokémon/capacité/méthode. Les capacités de départ sont distinguées du niveau positif exigé par RG09.
- La présence régionale implique une présence documentée mais ne suppose pas forcément une zone de rencontre ; l'inverse est garanti pour les opérations prévues par RG07.
- Les descriptions géographiques enrichies sont des synthèses des données disponibles, pas des descriptions officielles PokéAPI.
- Les valeurs manquantes ne sont pas remplacées arbitrairement. Les habitats absents et l'absence de rencontres pour certaines régions peuvent refléter des limites de couverture de la source.
- Les tests concurrentiels, les changements d'identifiants primaires et certains scénarios administratifs ne sont pas couverts par les validations exécutées. La base n'est pas déclarée prête pour la production.

## Suite

Ajouter des requêtes de consultation, documenter les résultats, puis concevoir les contrats d'une API et une interface. Prévoir une séparation entre accès aux données, logique applicative et présentation. Évaluer les extensions du modèle seulement si les usages ou l'API les justifient.
