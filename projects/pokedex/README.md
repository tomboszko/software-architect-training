# Pokédex — fil rouge de formation en architecture logicielle

**Projet pédagogique indépendant · novembre 2026 · en cours**

J'ai choisi librement Pokémon comme domaine d'étude. Ce choix est arbitraire : l'enjeu n'est pas de reproduire un jeu, mais de disposer d'un univers suffisamment riche pour travailler la modélisation de données, les relations complexes, les règles métier, SQL, puis la conception d'une application.

Le projet accompagne ma formation AI-Driven Software Architect à Technofutur TIC. Il s'agit d'un exercice personnel et non du projet final officiel de la formation. J'utilise Looping pour construire et ajuster le modèle, PostgreSQL 18 et pgAdmin pour la validation, Python pour les imports, et PokéAPI comme source principale de données. Les outils d'assistance IA contribuent à la rédaction des scripts et à leur revue ; les décisions de modélisation, l'intégration dans Looping et les exécutions locales sont documentées au fur et à mesure.

## 1. Du besoin au modèle conceptuel

Le Pokédex doit permettre de consulter les fiches des Pokémon, leurs types, talents, capacités et évolutions, de les situer dans un contexte géographique et de gérer les découvertes d'un dresseur. Le domaine offre plusieurs cas utiles : associations binaires et ternaires, cardinalités minimales et maximales, relations source/cible, attributs optionnels et intégrité entre tables.

J'ai construit le MCD dans Looping, puis revu les entités, les associations, leurs cardinalités et le dictionnaire de données. Le passage du MCD au MLD permet de traduire ces choix en tables et clés.

- [Modélisation et décisions](model/README.md)
- [Script initial pour Looping](model/looping-initial.txt) — archive historique, pas le schéma de référence.
- [Export final Looping](model/export-looping.sql) — export SQL brut de référence.
- [Script SQL final lisible](sql/01_schema.sql) — même structure et règles, présentées avec une indentation adaptée à la lecture.

La capture authentique du MCD intermédiaire (13 novembre) a été retrouvée. Son intégration binaire au dépôt reste à faire ; elle montre notamment l'ancien nom `REQUERIR_CONDITION`, avant le renommage en `ETRE_POSSIBLE_SI`. La capture finale actualisée et le fichier natif Looping (.loo) restent aussi à déposer lorsqu'ils seront disponibles.

## 2. Du modèle au SQL

Le résultat actuel comporte **13 entités principales, 14 associations conceptuelles et 22 tables relationnelles** (13 tables principales et 9 tables d'association). L'export contient 22 clés primaires, 24 clés étrangères, 13 identifiants SERIAL, 19 contraintes CHECK, 8 fonctions de trigger et 11 triggers explicites.

La démarche consiste à maintenir Looping comme source du modèle et de ses règles SQL. Les contraintes locales sont exprimées par NOT NULL, UNIQUE, CHECK et les clés ; les règles inter-tables nécessitent des fonctions PostgreSQL et des triggers, parfois différés à la fin de la transaction.

J'ai rencontré un problème de génération du SQL personnalisé : certains blocs étaient rendus sur une seule ligne sans séparateurs suffisants. Les correctifs ont été intégrés dans Looping, le script a été régénéré et la version destinée à la lecture a été reformatée sans intention de changer sa logique. Le renommage d'une association a aussi laissé une ancienne table dans la base de développement ; le nettoyage ciblé a permis de recréer le schéma.

## 3. Audit et validation

Les tests ont été exécutés sur la base locale `pokedex_dev`. Ils couvrent les cas acceptés et les rejets attendus, avec vérification des contraintes différées et annulation des données de test.

| Batterie | Résultat observé |
| --- | --- |
| [Validation fonctionnelle](sql/tests/validation.sql) | 18 vérifications PASS, 0 échec, 299 ms |
| [Réaffectations](sql/tests/reaffectations.sql) | 6 scénarios métier PASS, 0 échec, 159 ms |

Les deux exécutions se terminent par ROLLBACK. Les deux messages de préparation/initialisation de la seconde batterie ne sont pas comptés comme scénarios métier supplémentaires. Ces temps sont des observations locales, pas des mesures de performance généralisables.

Les tests de concurrence n'ont pas été effectués : j'ai choisi de clôturer cette phase et de poursuivre le projet. Ces résultats ne constituent pas une certification de robustesse pour tous les niveaux d'isolation, opérations administratives ou usages concurrents.

## 4. Peuplement et qualité des données

La base a d'abord été peuplée avec les 151 espèces de Kanto, puis étendue aux neuf générations. Les imports procèdent par dépendances : référentiels, fiches et relations, évolutions et conditions, apprentissages, géographie. Les Pokémon sont associés à leurs types et talents dans la même transaction, conformément aux règles métier. Les évolutions sont créées avec leurs conditions.

Le [dossier des importeurs](importers/) archive les scripts Python réellement utilisés. Les descriptions complémentaires et les dates de génération font l'objet d'un enrichissement distinct, documenté dans [ce script SQL](sql/enrichment/enrichissement_documente.sql).

L'[audit de complétude](sql/audit/completude.sql) a notamment permis d'identifier les informations manquantes et de cibler les enrichissements. Un [audit d'intégrité](sql/audit/integrite.sql) et une [réparation des présences régionales strictement déductibles](sql/repair/presences_regionales.sql) sont ajoutés comme outils de maintenance : ces deux nouveaux scripts restent à exécuter localement.

Voir [le bilan détaillé et les limites](docs/bilan.md).

## 5. Reproduire le travail

1. Installer PostgreSQL 18 et créer une base de développement dédiée, nommée `pokedex_dev`.
2. Sur une base vierge, exécuter **une seule** version du schéma : `sql/01_schema.sql` ou l'export brut. Ne pas exécuter les deux successivement.
3. Pour reproduire les validations existantes, exécuter les scripts de tests séparément sur une base de développement dédiée, avant le peuplement.
4. Installer Python et les dépendances : `py -m pip install requests "psycopg[binary]"`.
5. Depuis `importers/`, lancer `py .\\import_pokedex_global.py --phase tout`. Les quatre importeurs de base doivent rester dans le même dossier. Les scripts demandent le mot de passe PostgreSQL ou utilisent les variables PGHOST, PGPORT, PGUSER, PGPASSWORD selon leur configuration.
6. Exécuter l'audit de complétude, puis les enrichissements ciblés si nécessaire. Le cache et les réponses API ne sont pas versionnés.

Les scripts dans `sql/history/` et `model/correctifs-regles-looping.txt` sont conservés pour expliquer l'évolution de la conception. Ils ne sont pas des migrations à appliquer après le schéma final.

## 6. Suite du fil rouge

| Jalon | État |
| --- | --- |
| Modélisation Looping, MLD, règles et génération SQL | Réalisé |
| Création PostgreSQL et tests métier | Réalisé sur la base locale |
| Import PokéAPI et enrichissement | Réalisé ; couverture limitée par la source et le modèle |
| Requêtes SQL de consultation et d'analyse | En cours |
| Fiche Pokémon complète (types, talents, stats, capacités, évolutions, géographie) | À développer |
| API pour interroger la base | Prévue |
| Interface de recherche, affichage et suivi des découvertes | Prévue |
| Enrichissement PokéAPI et éventuelles adaptations du modèle | À étudier selon les besoins |

La prochaine étape est de construire progressivement une bibliothèque de [requêtes SQL](queries/README.md) pour maîtriser les jointures, les agrégations et les recherches. Ces requêtes pourront ensuite servir de base à une API, puis à une interface utilisateur. La technologie et l'architecture de ces couches seront choisies et justifiées plus tard ; ASP.NET Core est une piste cohérente avec la formation, sans engagement d'implémentation à ce stade.

## Sources et publication

- [Looping](https://www.looping-mcd.fr/) — outil de modélisation.
- [PostgreSQL 18](https://www.postgresql.org/docs/18/) — base de données.
- [PokéAPI v2](https://pokeapi.co/docs/v2) — source principale des données.
- Les autres sources utilisées pour les dates et descriptions sont citées dans le script d'enrichissement.

Pokémon et ses contenus appartiennent à leurs ayants droit. Ce dépôt documente un exercice indépendant, sans affiliation. Il n'inclut ni dump de la base, ni cache API, ni identifiants de connexion, ni données personnelles de dresseurs réels. Les illustrations officielles et les textes récupérés ne sont pas republiés en masse. Le projet reste en développement.
