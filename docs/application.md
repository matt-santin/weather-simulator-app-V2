# Application : stockage de service et site

Le site de la V1 (formulaire, page de résultats, documentation), branché sur les données de la V2. Code dans `src/app/` (serveur) et `web/` (pages), stockage construit par `src/store/build.py`.

## 1. Ce qui est servi

| Période | Source | Origine affichée |
|---|---|---|
| 1970-2025 | ERA5 ; températures : E-OBS (ERA5-Land ou ERA5 là où il manque) | réanalyse et observations |
| 2026 | rien : « Données indisponibles » | |
| 2027-2100 | CORDEX corrigé (`docs/correction.md`) : MPI-ESM1-2-HR / ICON-CLM, EUR-12, SSP3-7.0 | simulation, avec avertissement |

- Une recherche porte sur 92 jours au plus, à l'intérieur d'une seule période. Une plage qui touche 2026, ou qui chevauche 2025 et 2026, est refusée entière.
- Hors du domaine CORDEX : « Lieu hors de la zone couverte (Europe) ».
- Variables lues : `tasmax`, `tasmin`, `tas`, `pr`, `clt`, `hurs`, `sfcWind`. Règles d'affichage reprises de la V1 (classe de ciel, neige, bandes de température, chaleur humide) ; vent moyen à la place du vent maximal ; température humide calculée à partir de `tas` et `hurs`.
- Comparaison aux normales de saison : voir section 5.
- Simulation : MPI-ESM1-2-HR / ICON-CLM (`docs/choix_modele_cmip6.md`, `docs/correction.md` section 10), servie depuis le 10/10/2026 à la place d'EC-EARTH / RCA4. Le serveur lit la simulation dans le stockage (attribut `simulation`), pas dans son code.
- Données E-OBS : usage non commercial seulement (`docs/correction.md`, section 11). Le site est gratuit et non commercial ; la documentation porte les remerciements demandés et la référence Cornes et al. (2018).

## 2. Deux grilles

| Grandeurs | Grille | Passé | Futur |
|---|---|---|---|
| `tas`, `tasmax`, `tasmin` | 0,1°, terres | E-OBS, repli ERA5-Land | CORDEX corrigé contre la même référence |
| `tas`, `tasmax`, `tasmin` (lieux sans maille 0,1°, cartes) | 0,25° | E-OBS, repli ERA5 | CORDEX corrigé contre la même référence |
| les autres | 0,25° | ERA5 | CORDEX corrigé contre ERA5 |

Les températures passées et futures sont calées sur E-OBS depuis le 13/10/2026 (`docs/correction.md`, section 11), sur ERA5-Land auparavant. Le repli est fixé maille par maille pour toute la période, passé et futur : Afrique du Nord et Proche-Orient, est du domaine au-delà de 45° E, mailles où E-OBS manque plus de 1 % des jours, mer. À 0,1°, 110 912 mailles de terre sur 295 579 sont sur E-OBS ; à 0,25°, 17 631 sur 46 390. Aux limites du masque, les températures sautent de 0,7 à 1 K de plus qu'entre mailles voisines ordinaires (Russie, sud de la Turquie, mer d'Azov).

Un lieu prend ses températures dans la maille 0,1° la plus proche si elle est à 0,1° au plus (en latitude et en longitude), sinon dans sa maille 0,25° ; le reste vient toujours de la maille 0,25°. 99,9 % des mailles 0,25° majoritairement terrestres ont une maille 0,1° ; les petites îles (île d'Yeu, Belle-Île, Lampedusa) restent à 0,25°. La source de chaque journée le dit, d'après le masque de la maille lue : « E-OBS (températures), ERA5 », « ERA5-Land (températures), ERA5 » ou « ERA5 ». Même libellé pour la référence des journées simulées et pour le diagramme climatique.

Limite connue : en vallée étroite, la maille 0,1° la plus proche peut couvrir surtout les versants (Chamonix, 1 035 m : la maille 45,9 N 6,9 E est à 2 456 m d'altitude moyenne dans E-OBS ; Tx moyen de juillet 2015-2025 13,5 °C). Piste : choisir, parmi les mailles voisines, celle dont l'altitude est la plus proche de celle de la commune.

## 3. Stockage de service

`data/serve/point.zarr`, Zarr v3, copie de service des fichiers annuels : il se supprime et se reconstruit à tout moment.

| Groupe | Contenu | Période | Taille |
|---|---|---|---|
| `cordex` | CORDEX corrigé, 7 variables et `psl`, 0,25° | 1970-2100 | 21 Go |
| `era5` | ERA5, 7 variables et `psl` (`msl`) ; températures E-OBS ou repli ERA5, 0,25° | 1970-2025 | 8,4 Go |
| `cordex010` | CORDEX corrigé, 3 températures, 0,1° | 1970-2100 | 26 Go |
| `era5land` | 3 températures, E-OBS ou repli ERA5-Land, 0,1° | 1970-2025 | 10 Go |
| racine | `latitude`, `longitude`, `domain`, `eobs` (0,25°) ; `latitude010`, `longitude010`, `domain010`, `eobs010` (0,1°) | | |

Les noms `era5` et `era5land` sont gardés quelle que soit la référence : chaque tableau dit ce qu'il contient, ou ce contre quoi il est corrigé, dans son attribut `reference` (`name`, `version`, `fallback` : par exemple E-OBS, v33.0e, ERA5-Land). `eobs` et `eobs010` valent 1 là où les températures viennent d'E-OBS, 0 pour le repli (`source.nc` de la référence). Les groupes `cordex_rca4` et `cordex010_rca4` (46 Go) gardent l'ancienne simulation, en attendant leur suppression.

- Un bloc contient toute la période pour 2 × 2 mailles : une série en un point, de 3 mois ou de 131 ans, coûte un bloc par variable (2 à 50 ms). Blocs regroupés en paquets de 20 × 20 mailles.
- Valeurs en entiers de 16 bits : pas de 0,01 (°C, %, m/s), 0,1 mm/j pour `pr`, 0,1 hPa pour `psl`. Filtre delta en temps, compression zstd.
- ERA5 et ERA5-Land sont rangés sous les noms et unités de CORDEX, et masqués au domaine CORDEX de leur grille.
- L'attribut `built` est écrit en dernier : un tableau sans lui est incomplet, et le serveur refuse de démarrer.

`WSA_MODEL=mpi WSA_REF=eobs python -m src.store.build <groupe> <variables>`, LaCie branché ; `WSA_MODEL` choisit la simulation, `WSA_REF=eobs` les températures calées sur E-OBS. `build reference` écrit l'attribut `reference` sur les tableaux construits avant lui. Journal dans `data/serve/build.log`. Durées pour une température (13/10/2026) : 2 à 3 min pour `era5`, 6 min pour `cordex`, 14 à 16 min pour `era5land`, 38 à 45 min pour `cordex010`. Reconstruction des températures : `data/serve/bascule_eobs.sh` (3 h 20 ; purge des instantanés Time Machine avant chaque variable, arrêt sous 15 Go libres), journal `bascule_eobs.log`. `data/serve` est exclu de Time Machine. Le stockage est copié sur le LaCie par `python -m src.archive` ; `--free` ne le supprime jamais du Mac.

## 4. Serveur

FastAPI, sans état. `uvicorn src.app.api.app:app --port 8765`.

| Appel | Rôle |
|---|---|
| `GET /api/config` | périodes servies, plage maximale, échelle des températures, adresse du géocodage, simulation servie |
| `GET /api/days?latitude&longitude&start&end` | la série journalière classée, ou un refus avec sa phrase |
| `GET /api/normals?latitude&longitude&start&end` | les normales (Tx, Tn, précipitations) aux mêmes dates, `reference` = 1971, 1981 ou 1991 (section 5), mêmes refus |
| `GET /api/climate?latitude&longitude&start&end&reference` | le diagramme climatique du lieu (section 6), mêmes refus |
| `GET /api/years?latitude&longitude&start&end&reference` | les mêmes dates chaque année de 1970 à 2100 (section 7), mêmes refus |
| `/`, `/resultats`, `/documentation` | les pages |

- Le stockage est ouvert au démarrage. Le serveur refuse de démarrer si un groupe ne couvre pas la période servie, si un tableau est incomplet (`built`), si les tableaux CORDEX ne décrivent pas tous la même simulation, si un tableau ne dit pas d'où viennent ses données (`reference`), ou si les températures viennent d'E-OBS sans masque.
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

- mêmes mailles que la série : températures du groupe `era5land` à 0,1° si le lieu en a une, sinon du groupe `era5` à 0,25° (E-OBS ou son repli) ; précipitations ERA5 à 0,25° ;
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

- Valeurs par année : température moyenne (`tas`, mêmes mailles que la série) et cumul de pluie (pluie journalière moyenne × nombre de jours) ; données passées (E-OBS pour les températures, ERA5) jusqu'en 2025, CORDEX corrigé à partir de 2027.
- Référence : la période du bandeau des normales (1991-2020 par défaut), mêmes dates, ERA5 : moyenne, écart-type interannuel (ddof = 1), cumul moyen.
- Couleur : écart en écarts-types, bleu (-3 σ), vert, jaune (la normale), orange, rouge (+3 σ), saturée au-delà. L'année est écrite en blanc ou en noir, celle des deux qui contraste le plus avec la tuile : au moins 4,5:1 sur toute l'échelle. La grille occupe toute la largeur du cadre ; tuiles et chiffres suivent la largeur de l'écran.
- Survol : légère surbrillance. Clic : une petite fenêtre blanche, ancrée à la tuile (au-dessus, ou en dessous faute de place), donne la température moyenne, écart à la référence, cumul et pourcentage de la normale, avec un commentaire, et un lien vers les mêmes dates cette année-là. Elle se ferme par sa croix, Échap ou un clic ailleurs ; le focus revient à la tuile.
- Commentaires, calculés par le serveur (seuils propres au projet, pas une norme) :
  - température : à moins de 0,5 σ, « proche de la normale » ; de 0,5 à 1,5 σ, « plus chaud » ou « plus froid » ; à partir de 1,5 σ, « bien plus chaud » ou « bien plus froid » ;
  - précipitations, rapport à la normale : sous 0,5, « bien plus sec » ; sous 0,8, « plus sec » ; jusqu'à 1,2, « proche de la normale » ; jusqu'à 1,5, « plus humide » ; au-delà, « bien plus humide ».

`GET /api/years?latitude&longitude&start&end&reference` (`src/app/api/years.py`, tuiles `web/static/js/matrix.js`), environ 0,1 s.

Limite visible : une marche entre 2025 et 2027, le modèle corrigé étant plus frais que les données passées sur 2015-2025 (section 9), effet du retard de réchauffement du modèle (ajustement sur la TRACC à décider).

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
- Sources, à 0,25° : ERA5 (1970-2025), températures E-OBS ou repli ERA5 ; CORDEX corrigé contre ces mêmes données (2027-2100). Pas de grille à 0,1°, réservée aux points. Les raccords du masque E-OBS peuvent se voir (Russie à l'est de 40° E, sud de la Turquie).
- Isobares (case « Isobares », `isobares=1` dans l'adresse) : pression au niveau de la mer (`psl` de CORDEX, `msl` d'ERA5), mer comprise, moyennée à 0,5° sur le cadre de la carte et lissée (filtre 1-2-1, deux passes) ; une ligne tous les 5 hPa, tracée par le navigateur (carrés marchants, `mapview.js`), étiquettes espacées. Une saison pèse 2 Mo.

Stockage `data/serve/map.zarr` (`python -m src.store.maps tasmax tasmin pr clt psl`, environ 1 min par grandeur, LaCie branché pour le masque) : copie de `point.zarr` découpée par paquets de 32 jours sur un quart du domaine, mêmes entiers (vérifiés égaux), attributs `simulation` et `reference` recopiés. Par grandeur, ERA5 et CORDEX : `tasmax` 0,81 + 1,6 Go, `tasmin` 0,83 + 1,6, `pr` 0,54 + 0,74, `clt` 1,4 + 1,8, `psl` 0,65 + 0,83 ; 10,7 Go en tout, plus `cordex_rca4` (5,6 Go, à supprimer). Facultatif : sans lui, le site tourne et la page des cartes le dit.

| Appel | Rôle |
|---|---|
| `GET /api/map/cells` | les mailles de la carte (lignes et colonnes de la grille), envoyées une fois |
| `GET /api/map/isobars?start&end` | pression au niveau de la mer à 0,5°, jours × lignes × colonnes, dixièmes de hPa ; grille dans les en-têtes |
| `GET /api/map/{grandeur}?start&end` | jours × mailles en entiers 16 bits, dixièmes de l'unité (°C, mm, %) ; -32768 : pas de valeur ; jours, mailles, premier jour et origine dans les en-têtes ; mêmes refus qu'une recherche |

Une saison pèse 3,5 Mo, 1,8 Mo compressée (gzip, comme toutes les réponses de plus de 1 ko) ; lecture en 0,02 s, réponse en 0,2 s en local. Contours et icône : `python -m src.store.outlines` (`web/static/geo/europe.json`, 133 ko ; `web/static/icons/europe.svg`, tracé depuis le masque de `map.zarr`).

## 9. Contrôles du 13/10/2026

Après la reconstruction sur E-OBS, contre le serveur local :

- Balayage de 888 lieux (grille de 1,5° × 2,5° et 18 lieux nommés), 797 dans le domaine : aucune erreur, aucune valeur manquante, sur `/api/days`, `/api/normals`, `/api/climate` et `/api/years` (étés 2003 et 2061, hiver 1987). Libellés conformes au masque : E-OBS à Paris, Grenoble, Ajaccio, Tromsø, aux Féroé ; repli ERA5-Land à Rabat, Volgograd, Malte ; ERA5 seul à Lampedusa, à l'île de Sein, en mer.
- Valeur servie égale au fichier corrigé : Paris (48,9 N 2,4 E), Tx du 6/8/2061, 45,91 °C. Paris, 25/7/2019 : 42,3 °C (station de Montsouris 42,6 °C).
- Continuité, moyenne 2015-2025, corrigé − données passées servies : Paris Tx −1,0 K, Tn −0,6 K ; Grenoble Tn −1,1 K ; Chamonix Tx d'hiver −1,5 K ; Ajaccio Tx d'été −2,1 K ; mer d'Azov Tx d'hiver −1,9 K, d'été +1,1 K ; Féroé, Malte, Lampedusa, île de Sein ±0,2 K.
- Temps de réponse : 0,02 à 0,07 s par appel ; carte d'une saison 0,02 s (3,5 Mo), isobares 0,06 s (2 Mo).
- Captures (Playwright) : accueil, documentation, résultats (Paris, Chamonix, Rabat ; 2003 et 2083), cartes (étés 2003, 2019, 2083 avec isobares ; hivers 1987 et 2090) ; aucune erreur JavaScript.

## 10. Tests

`python -m pytest` (162 tests au 13/10/2026) : tests Python (API sur un petit stockage construit à la volée par `tests/conftest.py`, règles d'affichage, pages) et suite JavaScript (`node --test`, si `node` est installé).
