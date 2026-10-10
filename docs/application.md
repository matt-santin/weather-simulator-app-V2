# Application : stockage de service et site

Le site de la V1 (formulaire, page de résultats, documentation), branché sur les données de la V2. Code dans `src/app/` (serveur) et `web/` (pages), stockage construit par `src/store/build.py`.

## 1. Ce qui est servi

| Période | Source | Origine affichée |
|---|---|---|
| 1970-2025 | ERA5 ; températures : ERA5-Land | réanalyse |
| 2026 | rien : « Données indisponibles » | |
| 2027-2100 | CORDEX corrigé (`docs/correction.md`) : EC-EARTH / RCA4, RCP4.5 | simulation, avec avertissement |

- Une recherche porte sur 92 jours au plus, à l'intérieur d'une seule période. Une plage qui touche 2026, ou qui chevauche 2025 et 2026, est refusée entière.
- Hors du domaine EUR-11 : « Lieu hors de la zone couverte (Europe) ».
- Variables lues : `tasmax`, `tasmin`, `tas`, `pr`, `clt`, `hurs`, `sfcWind`. Règles d'affichage reprises de la V1 (classe de ciel, neige, bandes de température, chaleur humide) ; vent moyen à la place du vent maximal ; température humide calculée à partir de `tas` et `hurs`.
- Comparaison aux normales de saison : voir section 5.
- Changement de modèle décidé le 6/10/2026 : MPI-ESM1-2-HR / ICON-CLM (EUR-12, SSP3-7.0, `docs/choix_modele_cmip6.md`) remplacera RCA4. Corrigé les 7 et 8/10/2026 (`docs/correction.md`, section 10) ; restent quelques décisions de correction et la reconstruction du stockage de service. D'ici là, le site sert RCA4.

## 2. Deux grilles

| Grandeurs | Grille | Passé | Futur |
|---|---|---|---|
| `tas`, `tasmax`, `tasmin` | 0,1°, terres | ERA5-Land | CORDEX corrigé contre ERA5-Land |
| les autres | 0,25° | ERA5 | CORDEX corrigé contre ERA5 |

Les températures passées et futures sont donc calées sur ERA5-Land, plus froid que les stations pour Tx (Paris, Tx moyen de juillet 2015-2025 : 25,1 °C contre 26,6 °C pour E-OBS). Choix gardé le 10/10/2026 pour la cohérence entre passé et futur (`docs/correction.md`, section 9).

Un lieu prend ses températures dans la maille 0,1° la plus proche si elle est à 0,1° au plus (en latitude et en longitude), sinon dans sa maille 0,25° ; le reste vient toujours de la maille 0,25°. 99,9 % des mailles 0,25° majoritairement terrestres ont une maille 0,1° ; les petites îles (île d'Yeu, Belle-Île, Lampedusa) restent à 0,25°. La source de chaque journée le dit : « ERA5-Land (températures), ERA5 » ou « ERA5 ».

Limite connue : en vallée étroite, la maille 0,1° la plus proche peut couvrir surtout les versants (Chamonix : Tx de juillet 2019 de 15,5 °C à la maille 45,9 N 6,9 E). Piste : choisir, parmi les mailles voisines, celle dont l'altitude est la plus proche de celle de la commune.

## 3. Stockage de service

`data/serve/point.zarr`, Zarr v3, copie de service des fichiers annuels : il se supprime et se reconstruit à tout moment.

| Groupe | Contenu | Période | Taille |
|---|---|---|---|
| `cordex` | CORDEX corrigé, 7 variables, 0,25° | 1970-2100 | 19 Go |
| `era5` | ERA5, 7 variables, 0,25° | 1970-2025 | 7,3 Go |
| `cordex010` | CORDEX corrigé contre ERA5-Land, 3 températures, 0,1° | 1970-2100 | 27 Go |
| `era5land` | ERA5-Land, 3 températures, 0,1° | 1970-2025 | 8,3 Go |
| racine | `latitude`, `longitude`, `domain` (0,25°) ; `latitude010`, `longitude010`, `domain010` (0,1°) | | |

- Un bloc contient toute la période pour 2 × 2 mailles : une série en un point, de 3 mois ou de 131 ans, coûte un bloc par variable (2 à 50 ms). Blocs regroupés en paquets de 20 × 20 mailles.
- Valeurs en entiers de 16 bits : pas de 0,01 (°C, %, m/s), 0,1 mm/j pour `pr`. Filtre delta en temps, compression zstd.
- ERA5 et ERA5-Land sont rangés sous les noms et unités de CORDEX, et masqués au domaine CORDEX de leur grille.
- L'attribut `built` est écrit en dernier : un tableau sans lui est incomplet, et le serveur refuse de démarrer.

`python -m src.store.build <groupe> <variables>`, LaCie branché ; journal dans `data/serve/build.log`. Durées : 4 à 8 min par variable pour `era5`, environ 11 min pour `cordex`, environ 13 min pour `era5land`, environ 33 min pour `cordex010`. Le stockage est copié sur le LaCie par `python -m src.archive` ; `--free` ne le supprime jamais du Mac.

## 4. Serveur

FastAPI, sans état. `uvicorn src.app.api.app:app --port 8765`.

| Appel | Rôle |
|---|---|
| `GET /api/config` | périodes servies, plage maximale, échelle des températures, adresse du géocodage |
| `GET /api/days?latitude&longitude&start&end` | la série journalière classée, ou un refus avec sa phrase |
| `GET /api/normals?latitude&longitude&start&end` | les normales (Tx, Tn, précipitations) aux mêmes dates, `reference` = 1971, 1981 ou 1991 (section 5), mêmes refus |
| `GET /api/climate?latitude&longitude&start&end&reference` | le diagramme climatique du lieu (section 6), mêmes refus |
| `GET /api/years?latitude&longitude&start&end&reference` | les mêmes dates chaque année de 1970 à 2100 (section 7), mêmes refus |
| `/`, `/resultats`, `/documentation` | les pages |

- Le stockage est ouvert au démarrage ; il vérifie que chaque groupe couvre la période servie.
- Le géocodage (nom vers coordonnées) reste fait par le navigateur, auprès d'Open-Meteo : c'est la seule dépendance extérieure.

| Fichier | Rôle |
|---|---|
| `src/app/store.py` | lecture du stockage, choix des mailles, périodes |
| `src/app/api/validation.py`, `errors.py` | règles de la recherche, refus |
| `src/app/api/pipeline.py`, `contract.py` | du stockage au JSON |
| `src/app/api/normals.py` | normales de saison |
| `src/app/api/climate.py` | diagramme climatique |
| `src/app/api/years.py` | matrice des années |
| `src/app/domain/` | règles d'affichage (V1) |
| `web/` | pages, feuille de style, modules JavaScript (V1, adaptés) |

## 5. Normales de saison

Sur la page de résultats, le bouton « Comparer aux normales de saison », dans un bandeau au-dessus du graphique, superpose en gris aux journées affichées, passées ou simulées, les normales du même lieu. Un menu du même bandeau propose trois périodes de référence : 1971-2000, 1981-2010 et 1991-2020 (par défaut). Le stockage commençant en 1970, il n'y en a pas d'antérieure ; la liste est servie par `/api/config` (`normals`, `normals_default`).

Ce qui est tracé :

- températures : une bande entre la Tn normale et la Tx normale ;
- précipitations : la courbe du cumul normal, sur le panneau du cumul. Pas de barres journalières : une pluie normale journalière (un peu chaque jour) ne ressemble à aucune journée réelle.

Calcul (`src/app/api/normals.py`), à la volée, sans précalcul (30 ans en un point : un bloc par variable) :

- mêmes mailles que la série : températures ERA5-Land à 0,1° si le lieu en a une, sinon ERA5 à 0,25° ; précipitations ERA5 à 0,25° ;
- la normale d'une date est la moyenne de toutes les valeurs de la période de référence situées à 7 jours au plus de ce jour du calendrier, quelle que soit l'année : fenêtre centrée de 15 jours, environ 450 valeurs ;
- calendrier de 366 jours, 29 février compris (8 années) ; la fenêtre passe le 1er janvier ;
- sommes et effectifs sont cumulés sur la fenêtre avant division : chaque valeur pèse autant.

La normale d'un jour futur est celle du climat observé sur la période de référence, pas celle du modèle. Une période inconnue est refusée (« Période de référence inconnue… »). Les normales ne vont pas dans le fichier CSV.

## 6. Diagramme climatique

Sous le graphique, le diagramme ombrothermique du lieu : douze mois moyennés sur 15 ans autour de l'année de la recherche (année du jour du milieu de la plage), et en gris la période de référence choisie dans le menu des normales (même menu, 1991-2020 par défaut).

- Fenêtre de 15 ans dans une seule source : décalée pour rester dans 1970-2025 (ERA5) ou 2027-2100 (CORDEX corrigé). 2020 donne 2011-2025, 2030 donne 2027-2041, 2098 donne 2086-2100. Une fenêtre simulée le dit (« une simulation, pas une prévision »).
- Par mois : température moyenne (`tas`), Tn et Tx moyennes, précipitations d'un mois moyen (pluie journalière moyenne × longueur moyenne du mois). Mêmes mailles que la série.
- Échelle de Bagnouls et Gaussen : 20 mm au niveau de 10 °C. Mois sec si P ≤ 2T (P en mm, T en °C), calculé par le serveur (`dry`) ; les mois secs sont teintés. Sources : Bagnouls et Gaussen (1957), repris par Charre, *Mappemonde* (https://www.mgm.fr/PUB/Mappemonde/M297/Charre.pdf).
- L'axe est cadré sur la plus haute des températures et des demi-pluies ; les degrés ne sont numérotés que jusqu'à la dizaine au-dessus du mois le plus chaud. Dans un lieu très arrosé, la courbe des températures est donc tassée en bas.
- Sous le diagramme : température annuelle, cumul annuel et mois secs, pour la fenêtre et pour la référence.

`GET /api/climate?latitude&longitude&start&end&reference` (`src/app/api/climate.py`, dessin `web/static/js/climate.js`), environ 0,1 s.

## 7. Matrice des années

Sous le diagramme, une tuile par année de 1970 à 2100, dix par ligne (une décennie par ligne), l'année écrite sur la tuile. Chaque année porte les mêmes dates que la recherche (le 29 février devient le 28) ; une année dont les dates sortent d'une période servie (2026, un hiver qui court sur 2026 ou au-delà de 2100) est hachurée et inactive. Les années simulées portent un liseré pointillé, de la couleur de leur chiffre.

- Valeurs par année : température moyenne (`tas`, mêmes mailles que la série) et cumul de pluie (pluie journalière moyenne × nombre de jours) ; ERA5 et ERA5-Land jusqu'en 2025, CORDEX corrigé à partir de 2027.
- Référence : la période du bandeau des normales (1991-2020 par défaut), mêmes dates, ERA5 : moyenne, écart-type interannuel (ddof = 1), cumul moyen.
- Couleur : écart en écarts-types, bleu (-3 σ), vert, jaune (la normale), orange, rouge (+3 σ), saturée au-delà. L'année est écrite en blanc ou en noir, celle des deux qui contraste le plus avec la tuile : au moins 4,5:1 sur toute l'échelle. La grille occupe toute la largeur du cadre ; tuiles et chiffres suivent la largeur de l'écran.
- Survol : légère surbrillance. Clic : une petite fenêtre blanche, ancrée à la tuile (au-dessus, ou en dessous faute de place), donne la température moyenne, écart à la référence, cumul et pourcentage de la normale, avec un commentaire, et un lien vers les mêmes dates cette année-là. Elle se ferme par sa croix, Échap ou un clic ailleurs ; le focus revient à la tuile.
- Commentaires, calculés par le serveur (seuils propres au projet, pas une norme) :
  - température : à moins de 0,5 σ, « proche de la normale » ; de 0,5 à 1,5 σ, « plus chaud » ou « plus froid » ; à partir de 1,5 σ, « bien plus chaud » ou « bien plus froid » ;
  - précipitations, rapport à la normale : sous 0,5, « bien plus sec » ; sous 0,8, « plus sec » ; jusqu'à 1,2, « proche de la normale » ; jusqu'à 1,5, « plus humide » ; au-delà, « bien plus humide ».

`GET /api/years?latitude&longitude&start&end&reference` (`src/app/api/years.py`, tuiles `web/static/js/matrix.js`), environ 0,1 s.

Limite visible : à Paris en été, 2027-2035 (CORDEX) sont plus frais que 2018-2025 (ERA5), effet du déficit de réchauffement du modèle.

## 8. Cartes

Page `/cartes`, reliée depuis l'accueil (en haut à droite : contour de l'Europe, « Cartes météos »). Une grandeur, une saison (printemps, été, automne, hiver, bornes du formulaire) et une année, dans l'adresse (`?grandeur=tasmax&saison=summer&annee=2100`, Tx de l'été 2100 par défaut), sur l'Europe. Grandeurs : températures maximales et minimales, précipitations, nébulosité ; la page ne propose que celles que le stockage contient (`variables` de `/api/map/cells`).

| Grandeur | Bandes | Panneau | Frise |
|---|---|---|---|
| Tx | celles du site (5 °C, `/api/config`), 40 °C et plus hachuré | maille la plus chaude, médiane | médiane |
| Tn | 5 °C de -20 à 30 °C (12 couleurs : violets sous -5 °C, bleus jusqu'à 0 °C, orange et rouge au-dessus de 20 °C, seuil des nuits chaudes de `figures/climat/france_indicateurs.py`) | maille la plus froide, médiane | médiane |
| Précipitations | moins de 1 mm (sec : seuil d'un jour de pluie, DRIAS et Météo-France), 1, 5, 10, 20, 50 mm et plus | maille la plus arrosée, part de mailles sèches | moyenne (la médiane est souvent nulle) |
| Nébulosité | par 20 % | médiane, part de mailles à moins de 20 % | médiane |

- Carte jour par jour (Tx, Tn et pluie : valeur du jour ; nébulosité : moyenne du jour), mailles terrestres de 0,25° (masque terre-mer ERA5 ≥ 0,5, dans le domaine CORDEX), cadre 25° O à 45° E, 34° N à 72° N : 19 249 mailles. Projection azimutale équivalente de Lambert centrée sur 52° N, 10° E (celle des cartes statistiques européennes, ETRS89-LAEA), sur la sphère : méridiens convergents, parallèles courbes, quadrillage tous les 10° ; chaque maille est dessinée en quadrilatère, et la carte est cadrée sur les mailles présentes. Contours des pays : Natural Earth 1:50m (domaine public).
- Mise en page sur ordinateur (1000 px et plus) : trois colonnes, réglages et lecteur à gauche, carte au centre sur toute la hauteur de la fenêtre, lecture du jour à droite ; rien au-dessus ni au-dessous de la carte. En dessous de 1000 px, tout s'empile.
- Lecture, jour précédent et suivant, vitesse (1, 3 ou 8 jours par seconde), frise des jours (souris ou flèches du clavier). Survol : valeur et coordonnées de la maille. Panneau : les deux chiffres du tableau ci-dessus, répartition par bande. Mention « simulation » pour 2027-2100. Retour au site en haut à droite : soleil et nuage en traits (`web/static/icons/weather.svg`) et « Weather Simulator ». Zoom : molette, double-clic, pincement, boutons + et − et « voir toute l'Europe » ; glisser pour se déplacer, jusqu'à ×12 (on voit alors les mailles de 0,25°).
- Sources : ERA5 (1970-2025), CORDEX corrigé contre ERA5 (2027-2100), à 0,25° ; pas ERA5-Land, réservé aux points.

Stockage `data/serve/map.zarr` (`python -m src.store.maps tasmax tasmin pr clt`, environ 1 min par grandeur, LaCie branché pour le masque) : copie de `point.zarr` découpée par paquets de 32 jours sur un quart du domaine, mêmes entiers (vérifiés égaux). Par grandeur, ERA5 et CORDEX : `tasmax` 0,67 + 1,68 Go, `tasmin` 0,70 + 1,71, `pr` 0,56 + 0,59, `clt` 1,47 + 2,04 ; 8,8 Go en tout. Facultatif : sans lui, le site tourne et la page des cartes le dit.

| Appel | Rôle |
|---|---|
| `GET /api/map/cells` | les mailles de la carte (lignes et colonnes de la grille), envoyées une fois |
| `GET /api/map/{grandeur}?start&end` | jours × mailles en entiers 16 bits, dixièmes de l'unité (°C, mm, %) ; -32768 : pas de valeur ; jours, mailles, premier jour et origine dans les en-têtes ; mêmes refus qu'une recherche |

Une saison pèse 3,5 Mo, 1,8 Mo compressée (gzip, comme toutes les réponses de plus de 1 ko) ; lecture en 0,02 s, réponse en 0,2 s en local. Contours et icône : `python -m src.store.outlines` (`web/static/geo/europe.json`, 133 ko ; `web/static/icons/europe.svg`, tracé depuis le masque de `map.zarr`).

## 9. Tests

`python -m pytest` : tests Python (API sur un petit stockage construit à la volée par `tests/conftest.py`, règles d'affichage, pages) et suite JavaScript (`node --test`, si `node` est installé).
