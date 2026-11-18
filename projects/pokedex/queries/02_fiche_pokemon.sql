-- Fiche Pokémon : affichage vertical des informations.
-- Modifier le nom dans la clause WHERE pour consulter un autre Pokémon.
-- Lecture seule ; les branches évolutives sont séparées par un saut de ligne.

SELECT
    info.libelle AS information,
    info.valeur AS valeur
FROM pokemon p
JOIN generation g
    ON g.id_generation = p.id_generation

CROSS JOIN LATERAL (
    VALUES
        (1, 'Numéro Pokédex', p.id_pokemon::TEXT),
        (2, 'Nom', p.nom_pokemon),
        (3, 'Catégorie', p.categorie_pokedex),
        (4, 'Description', p.description_pokedex),
        (5, 'Génération', g.nom_generation),
        (6, 'Taille (m)', p.taille_m::TEXT),
        (7, 'Poids (kg)', p.poids_kg::TEXT),

        (8, 'Types', (
            SELECT STRING_AGG(t.nom_type, ' / ' ORDER BY pt.position_type)
            FROM posseder_type pt
            JOIN type t ON t.id_type = pt.id_type
            WHERE pt.id_pokemon = p.id_pokemon
        )),

        (9, 'Talents', (
            SELECT STRING_AGG(
                t.nom_talent ||
                CASE WHEN at.est_cache THEN ' (caché)' ELSE '' END,
                ', '
            )
            FROM avoir_talent at
            JOIN talent t ON t.id_talent = at.id_talent
            WHERE at.id_pokemon = p.id_pokemon
        )),

        (10, 'Points de vie', p.pv_base::TEXT),
        (11, 'Attaque', p.attaque_base::TEXT),
        (12, 'Défense', p.defense_base::TEXT),
        (13, 'Attaque spéciale', p.attaque_speciale::TEXT),
        (14, 'Défense spéciale', p.defense_speciale::TEXT),
        (15, 'Vitesse', p.vitesse_base::TEXT),

        (16, 'Total statistiques', (
            p.pv_base +
            p.attaque_base +
            p.defense_base +
            p.attaque_speciale +
            p.defense_speciale +
            p.vitesse_base
        )::TEXT),

        (17, 'Habitats', (
            SELECT STRING_AGG(h.nom_habitat, ', ')
            FROM vivre_habitat vh
            JOIN habitat h ON h.id_habitat = vh.id_habitat
            WHERE vh.id_pokemon = p.id_pokemon
        )),

        (18, 'Régions', (
            SELECT STRING_AGG(r.nom_region, ', ')
            FROM apparaitre_region ar
            JOIN region r ON r.id_region = ar.id_region
            WHERE ar.id_pokemon = p.id_pokemon
        )),

        (19, 'Nombre de capacités', (
            SELECT COUNT(DISTINCT ac.id_capacite)::TEXT
            FROM apprendre_capacite ac
            WHERE ac.id_pokemon = p.id_pokemon
        )),

        (20, 'Chaîne d''évolution', (
            WITH RECURSIVE

            -- Remonter jusqu'au Pokémon d'origine
            ancetres AS (
                SELECT p.id_pokemon

                UNION

                SELECT e.id_pokemon_source
                FROM evolution e
                JOIN ancetres a
                    ON e.id_pokemon_cible = a.id_pokemon
            ),

            -- Identifier la racine de la famille
            racines AS (
                SELECT a.id_pokemon
                FROM ancetres a
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM evolution e
                    WHERE e.id_pokemon_cible = a.id_pokemon
                )
            ),

            -- Construire toutes les chaînes d'évolution
            chaines AS (
                SELECT
                    pk.id_pokemon,
                    pk.nom_pokemon::TEXT AS chaine,
                    ARRAY[pk.id_pokemon] AS visites
                FROM pokemon pk
                JOIN racines r
                    ON r.id_pokemon = pk.id_pokemon

                UNION ALL

                SELECT
                    suivant.id_pokemon,
                    ch.chaine || ' -> ' || suivant.nom_pokemon,
                    ch.visites || suivant.id_pokemon
                FROM chaines ch
                JOIN evolution e
                    ON e.id_pokemon_source = ch.id_pokemon
                JOIN pokemon suivant
                    ON suivant.id_pokemon = e.id_pokemon_cible
                WHERE suivant.id_pokemon <> ALL(ch.visites)
            )

            -- Afficher uniquement les chaînes complètes
            SELECT COALESCE(
                STRING_AGG(
                    CASE
                        WHEN CARDINALITY(ch.visites) = 1
                        THEN ch.chaine || ' (aucune évolution)'
                        ELSE ch.chaine
                    END,
                    E'\n' ORDER BY ch.chaine
                ),
                'Chaîne non disponible'
            )
            FROM chaines ch
            WHERE NOT EXISTS (
                SELECT 1
                FROM evolution e
                WHERE e.id_pokemon_source = ch.id_pokemon
            )
        )),

        (21, 'Image', p.url_image)

) AS info(ordre, libelle, valeur)

WHERE p.nom_pokemon ILIKE 'Pikachu'

ORDER BY info.ordre;
