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

`python -m src.store.build <groupe> <variables>`, LaCie branché ; `WSA_MODEL` choisit la simulation (MPI / ICON par défaut) ; les températures sont toujours celles d'E-OBS ou calées sur E-OBS. Journal dans `data/serve/build.log`. Durées pour une température (13/10/2026) : 2 à 3 min pour `era5`, 6 min pour `cordex`, 14 à 16 min pour `era5land`, 38 à 45 min pour `cordex010`. Reconstruction des températures : `data/serve/bascule_eobs.sh` (3 h 20 ; purge des instantanés Time Machine avant chaque variable, arrêt sous 15 Go libres), journal `bascule_eobs.log`. `data/serve` est exclu de Time Machine. Le stockage est copié sur le LaCie par `python -m src.archive` ; `--free` ne le supprime jamais du Mac.

## 4. Serveur

FastAPI, sans état. `uvicorn src.app.api.app:app --port 8765`.

| Appel | Rôle |
|---|---|
| `GET /api/config` | périodes servies, plage maximale, échelle des températures, adresse du géocodage, simulation servie |
| `GET /api/days?latitude&longitude&start&end` | la série journalière classée, ou un refus avec sa phrase |
| `GET /api/normals?latitude&longitude&start&end` | les normales (Tx, Tn, précipitations) aux mêmes dates, `reference` = 1971, 1981 ou 1991 (section 5), mêmes refus |
| `GET /api/climate?latitude&longitude&start&end&reference` | le diagramme climatique du lieu (section 6), mêmes refus |
| `GET /api/years?latitude&longitude&start&end&reference` | les mêmes dates chaque année de 1970 à 2100 (section 7), mêmes refus |
| `GET /api/kinds?latitude&longitude&start&end` | les saisons de chaque époque du formulaire, classées en fraîches, normales et chaudes (section 11), mêmes refus |
| `GET /api/covered?latitude&longitude` (répétés, 20 points au plus) | pour chaque point, s'il est dans le domaine servi : le formulaire ne propose que les lieux qu'une recherche accepterait |
| `GET /api/card.png?latitude&longitude&start&end` | l'image d'aperçu d'une recherche partagée (section 14), mêmes refus qu'une recherche |
| `GET /api/health` | le serveur répond : `status`, date de construction du stockage, cartes et lieux servis ou non ; jamais mis en cache |
| `/`, `/resultats`, `/documentation` | les pages |

- Le stockage est ouvert au démarrage. Le serveur refuse de démarrer si un groupe ne couvre pas la période servie, si un tableau est incomplet (`built`), si les tableaux CORDEX ne décrivent pas tous la même simulation, si un tableau ne dit pas d'où viennent ses données (`reference`), ou si les températures viennent d'E-OBS sans masque.
- Lectures (13/11/2026) : la série entière d'une variable en une maille est gardée en mémoire après sa première lecture, en entiers de 16 bits (256 séries au plus, environ 25 Mo, soit une douzaine de lieux ; `KEPT` dans `src/app/store.py`). Les six appels d'une page relisaient les mêmes blocs : pour un lieu jamais lu, les six passent de 380 ms à 80 ms en local (médiane de 8 villes). Le serveur ne charge plus xarray, dask ni la chaîne de correction (import en 0,4 s au lieu de 1,2 s).
- Cache (13/11/2026) : chaque réponse 200 de l'API porte `Cache-Control: public, max-age=3600` (les cartes gardent leur journée) et un `ETag` tiré de la date de construction des stockages, de la liste des lieux et du code du serveur ; une demande dont la marque tient encore (`If-None-Match`) reçoit un 304, sans lecture. Un refus n'est pas gardé. Après une reconstruction ou une mise à jour du code, un navigateur peut montrer l'ancienne réponse une heure au plus. Les fichiers statiques restent revalidés à chaque visite (`no-cache`).
- Journal (13/11/2026) : au démarrage, le serveur écrit ce qu'il sert (stockage, date de construction, simulation, grandeurs des cartes, nombre de lieux), avec l'heure, à côté des lignes d'uvicorn.
- Dépendances (13/11/2026) : `requirements-server.txt` suffit au serveur (fastapi, uvicorn, numpy, zarr) ; `requirements.txt` l'inclut et ajoute la chaîne de données, les figures et les tests. Versions exactes de l'environnement du 13/11/2026 (Python 3.14).
- Le géocodage (nom vers coordonnées) reste fait par le navigateur, auprès d'Open-Meteo : c'est la seule dépendance extérieure.
- Page de résultats : les journées en calendrier de 7 colonnes (lundi à dimanche), 4 semaines visibles au plus (moins si la fenêtre est trop basse), le reste par défilement vertical calé par semaine ; chaque tuile porte sa date, le pictogramme du ciel et sa Tx, sur un fond teinté selon la classe de cette Tx (10 classes de 5 °C depuis le 07/11/2026, de moins de 0 °C à 40 °C et plus : bleu profond (< 0 °C, jour sans dégel, TXFD de DRIAS), bleu, turquoise, vert, jaune, orange clair, orange, rouge, bordeaux, noir doux #1a1a1a (≥ 40 °C) ; couleurs décalées d'une classe vers le froid par rapport à l'échelle de 9 classes de 5 à 40 °C ; encre blanche sous 0 °C et à partir de 30 °C ; légende chiffrée sous le calendrier, bornes lues dans `/api/config`) ; chaque mois s'ouvre sur une ligne à son nom (« juillet 2044 », entre deux filets), la semaine étant coupée au dernier jour du mois précédent ; le premier jour simulé porte la mention « simulation ». Au survol, au focus ou au toucher, une copie agrandie de la tuile donne le ciel en toutes lettres et un tableau à taille égale : température max., température min., précipitations, humidité relative (moyenne journalière, `hurs`), vent moyen. Une seule tuile dans l'ordre de tabulation, les flèches pour passer d'un jour à l'autre. Sous 60rem de large, une liste d'une ligne par jour avec tout affiché, sans défilement propre ni agrandissement Habillage du 04/11/2026 (`web/static/css/style.css`, fin du fichier) : en-tête sur toute la largeur, au dégradé de sa saison depuis le 05/11/2026 (bleu l'hiver, vert-jaune au printemps, orange-rouge l'été, orange-brun l'automne, partie colorée des dégradés d'avant le 17/10, encre sombre de la saison à 5:1 au moins ; bleu nuit de l'accueil du 04/11 au 05/11), fond gris clair, chaque partie (calendrier, graphique, diagramme climatique, matrice des années) sur une carte blanche à coins arrondis, titres en Garamond, encres ardoise communes aux quatre saisons ; matrice des années en échelle divergente bleu, blanc, rouge (écart en écarts-types, saturé à 3, inchangé), années simulées marquées d'un point. Contrastes mesurés : 4,5:1 au moins partout (tuiles du calendrier de 5,7:1 à 13,8:1). Structure, contenu et interactions inchangés (`web/static/js/band.js`, `dayzoom.js`, `matrix.js`).

| Fichier | Rôle |
|---|---|
| `src/app/store.py` | lecture du stockage, choix des mailles, périodes |
| `src/app/api/validation.py`, `errors.py` | règles de la recherche, refus |
| `src/app/api/pipeline.py`, `contract.py` | du stockage au JSON |
| `src/app/api/normals.py` | normales de saison |
| `src/app/api/climate.py` | diagramme climatique |
| `src/app/api/years.py` | matrice des années |
| `src/app/api/kinds.py` | types de saison du formulaire |
| `src/app/domain/` | règles d'affichage (V1) |
| `web/` | pages, feuille de style, modules JavaScript (V1, adaptés) |

Réorganisation du 05/11/2026 (lot 1 des pistes de sensibilisation) : ordre calendrier, matrice des années, graphique, diagramme climatique (le 06/11 : synthèse, calendrier, graphique, matrice, diagramme ; lien « Voir cette saison parmi toutes les années » dans la synthèse) ; l'avertissement n'est plus un encadré orange mais une ligne « Simulation : une météo plausible, pas une prévision. » avec un « ? » qui donne le détail ; normales affichées d'office sur le graphique (le bouton les retire) ; l'année affichée entourée dans la matrice ; méthode des normales, seuils de la matrice et critère de Bagnouls et Gaussen derrière un « ? » (`web/static/js/hint.js`) ; diagramme titré « Le climat du lieu, mois par mois ».

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
- L'axe est cadré sur la plus haute des températures et des demi-pluies ; les degrés ne sont numérotés que jusqu'à la dizaine au-dessus du mois le plus chaud. Dans un lieu très arrosé, la courbe des températures est donc tassée en bas : le dessin est plus haut depuis le 14/11/2026 (500 au lieu de 380 pour 1000 de large), l'échelle restant celle de Bagnouls et Gaussen.
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

Limite visible : une marche entre 2025 et 2027, le modèle corrigé étant plus frais que les données passées sur 2015-2025 (section 9), effet du retard de réchauffement du modèle. Elle reste : l'ajustement sur la TRACC est écarté le 13/11/2026 (`docs/choix_modele_cmip6.md`, section 5).

## 8. Cartes

Page `/cartes`, reliée depuis l'accueil (en haut à droite : contour de l'Europe, « Cartes météos »). Une grandeur, une saison (printemps, été, automne, hiver, bornes du formulaire) et une année, dans l'adresse (`?grandeur=tasmax&saison=summer&annee=2100`, Tx de l'été 2100 par défaut), sur l'Europe. Grandeurs : températures maximales et minimales, précipitations, nébulosité ; la page ne propose que celles que le stockage contient (`variables` de `/api/map/cells`).

| Grandeur | Bandes | Panneau | Frise |
|---|---|---|---|
| Tx | celles du site (5 °C de 0 à 40 °C, `/api/config`), mêmes couleurs que le calendrier depuis le 07/11/2026, 40 °C et plus (noir doux) hachuré | maille la plus chaude, médiane | médiane |
| Tn | 5 °C de -20 à 30 °C (12 couleurs : violets sous -5 °C, bleus jusqu'à 0 °C, orange et rouge au-dessus de 20 °C, seuil des nuits chaudes de `figures/climat/france_indicateurs.py`) | maille la plus froide, médiane | médiane |
| Précipitations | moins de 1 mm (sec : seuil d'un jour de pluie, DRIAS et Météo-France), 1, 5, 10, 20, 50 mm et plus | maille la plus arrosée, part de mailles sèches | moyenne (la médiane est souvent nulle) |
| Nébulosité | par 20 % | médiane, part de mailles à moins de 20 % | médiane |

- Carte jour par jour (Tx, Tn et pluie : valeur du jour ; nébulosité : moyenne du jour), mailles terrestres de 0,25° (masque terre-mer ERA5 ≥ 0,5, dans le domaine CORDEX), cadre 25° O à 45° E, 34° N à 72° N : 19 249 mailles. Projection azimutale équivalente de Lambert centrée sur 52° N, 10° E (celle des cartes statistiques européennes, ETRS89-LAEA), sur la sphère : méridiens convergents, parallèles courbes, quadrillage tous les 10° ; chaque maille est dessinée en quadrilatère, et la carte est cadrée sur les mailles présentes. Contours des pays : Natural Earth 1:50m (domaine public).
- Mise en page sur ordinateur (1000 px et plus) : trois colonnes, réglages et lecteur à gauche, carte au centre sur toute la hauteur de la fenêtre, lecture du jour à droite ; rien au-dessus ni au-dessous de la carte. En dessous de 1000 px, tout s'empile.
- Lecture, jour précédent et suivant (bouton rond plein, triangle pour lire, deux barres pour la pause, nom « Lecture » ou « Pause » pour les lecteurs d'écran, depuis le 07/11/2026), vitesse (1, 3 ou 8 jours par seconde), frise des jours (souris ou flèches du clavier). Survol : valeur et coordonnées de la maille. Panneau : répartition des mailles par bande (les deux chiffres de la colonne « Panneau » du tableau, maille extrême et médiane, retirés le 07/11/2026 : la maille la plus chaude tombait presque toujours dans le désert syrien). Mention « Simulation : une météo plausible, pas une prévision. », celle des résultats depuis le 07/11/2026, le scénario dans son « ? ». Mention « simulation » pour 2027-2100. Retour au site en haut à droite : soleil et nuage en traits (`web/static/icons/weather.svg`) et « Weather Simulator ». Zoom : molette, double-clic, pincement, boutons + et − et « voir toute l'Europe » ; glisser pour se déplacer, jusqu'à ×12 (on voit alors les mailles de 0,25°).
- Sources, à 0,25° : ERA5 (1970-2025), températures E-OBS ou repli ERA5 ; CORDEX corrigé contre ces mêmes données (2027-2100). Pas de grille à 0,1°, réservée aux points. Les raccords du masque E-OBS peuvent se voir (Russie à l'est de 40° E, sud de la Turquie).
- Isobares (case « Isobares », `isobares=1` dans l'adresse) : pression au niveau de la mer (`psl` de CORDEX, `msl` d'ERA5), mer comprise, moyennée à 0,5° sur le cadre de la carte et lissée (filtre 1-2-1, deux passes) ; une ligne tous les 5 hPa, tracée par le navigateur (carrés marchants, `mapview.js`), étiquettes espacées. Une saison pèse 2 Mo.

- Lien avec la page de résultats (07/11/2026, `web/static/js/links.js`) : la carte de synthèse des résultats porte « Voir cette saison sur la carte d'Europe » (même saison, même année, `&lieu&lat&lon` dans l'adresse), affiché seulement si le serveur a les cartes et que le lieu est dans leur cadre (`map_box` de `/api/config`, `null` sans `map.zarr`). Sur la carte, le lieu reçu est marqué d'un anneau ; le panneau donne sa valeur du jour (« À Lyon ») et un lien « Voir la saison à Lyon » qui suit la saison et l'année choisies sur la carte. Un clic sur une maille terrestre (une pression qui bouge de moins de 5 px ; un glisser reste un déplacement) ouvre une bulle : valeur du jour, localité la plus proche (« Près de Voreppe (France) », « Grenoble (France) » à moins de 3 km), coordonnées du point, lien « Voir cette saison ici » vers les résultats de ce point (la localité en nom de lieu, sinon les coordonnées). La bulle suit le jour affiché et le zoom ; croix ou Échap pour la fermer. La valeur de la bulle est celle de la maille de 0,25° ; les résultats lisent les températures à 0,1° : les deux peuvent différer d'un ou deux degrés en relief.
- Synchronisation au jour (07/11/2026) : dans le calendrier des résultats, un clic sur la dernière ligne de la tuile agrandie d'une journée, et sur elle seule (Entrée au clavier ; au toucher, un premier contact agrandit la tuile, un second sur cette ligne ouvre la carte ; à la souris, la tuile agrandie reste ouverte tant que le pointeur est sur elle ou sur la tuile, la molette sur elle fait défiler le calendrier) ouvre la carte d'Europe sur ce jour, à l'arrêt (`jour` dans l'adresse), dans la saison qui le contient ; la tuile agrandie l'annonce sur une dernière ligne (« Voir ce jour sur la carte d'Europe › »). Mêmes conditions que le lien de la synthèse, plus une saison que la carte propose ; rien sur la liste des écrans étroits. Sur la carte, les deux liens vers les résultats emportent le jour affiché, et l'adresse le garde quand la lecture est à l'arrêt (une carte partagée s'ouvre sur son jour). Arrivant avec `jour`, la page de résultats place la semaine de ce jour en haut du calendrier, le calendrier en haut de la fenêtre, une fois la synthèse posée, et ouvre la tuile du jour, cerclée de bleu.
- Barre commune (07/11/2026, essai, `web/static/js/nav.js`) : en haut des résultats et de la carte, sur le fond sombre de la carte (#17140f, encre 14:1, encre douce 8:1), toute la largeur, au-dessus du bandeau de saison des résultats. À gauche le soleil et « Weather Simulator » (accueil), à droite la saison montrée (« Été 2063 », « Hiver 2080-2081 ») et deux onglets : le lieu (« Lyon », haut des résultats) et « Carte » (la carte d'Europe de la même saison, le lieu marqué ; « Europe » jusqu'au 08/11/2026), l'onglet de la page courante plein. Onglet Carte aux mêmes conditions que le lien de la synthèse ; sans lieu, la carte n'a que l'onglet Carte. Le lien « Weather Simulator » du haut de la colonne droite de la carte passe dans la barre ; la carte occupe la hauteur restante. Sous 560 px : le soleil seul, sans la saison.
- Harmonisation avec les résultats (07/11/2026), fond sombre gardé : chiffres en Garamond, unité en petit à côté (`.unit` du calendrier) pour la valeur du lieu, de la bulle et du survol ; bulles de survol et de maille sur la carte claire des notes « ? » (#fbfaf7, encre #14202e, lien bleu #1d5fb4) ; boutons en pastille aux dimensions de ceux des résultats ; titre à la taille des titres de rubrique des résultats (1,75rem).
- Noms des lieux : `GET /api/place?latitude&longitude` donne la localité la plus proche (distance sur la sphère), son pays (code ISO, nom français dans le navigateur) et sa distance, ou rien au-delà de 50 km (mer, intérieur de la Scandinavie). Liste `data/serve/places.tsv` (690 ko, 20 330 lieux), construite par `python -m src.store.places` depuis GeoNames (`data/fixed/geonames/` : `cities5000.txt`, localités de 5 000 habitants et plus, et `alternate_fr.tsv`, noms français extraits d'`alternateNamesV2.txt` ; téléchargés le 07/11/2026, CC BY 4.0, attribution sur la page de documentation et sous la carte) : cadre de la carte, sans quartiers (PPLX), lieux historiques ni abandonnés ; nom français hors de France quand GeoNames en a un (Vienne, Bruxelles, Londres). Lue au démarrage, en mémoire, réponse en moins d'1 ms. Facultative : sans elle, `/api/place` répond 503 et la bulle ne montre que les coordonnées.

Stockage `data/serve/map.zarr` (`python -m src.store.maps tasmax tasmin pr clt psl`, environ 1 min par grandeur, LaCie branché pour le masque) : copie de `point.zarr` découpée par paquets de 32 jours sur un quart du domaine, mêmes entiers (vérifiés égaux), attributs `simulation` et `reference` recopiés. Par grandeur, ERA5 et CORDEX : `tasmax` 0,81 + 1,6 Go, `tasmin` 0,83 + 1,6, `pr` 0,54 + 0,74, `clt` 1,4 + 1,8, `psl` 0,65 + 0,83 ; 10,7 Go en tout, plus `cordex_rca4` (5,6 Go, à supprimer). Facultatif : sans lui, le site tourne et la page des cartes le dit. Un `map.zarr` présent mais inutilisable (incomplet, groupe manquant) est signalé dans le journal du serveur au démarrage (« cartes non servies »), le site tournant sans cartes.

| Appel | Rôle |
|---|---|
| `GET /api/map/cells` | les mailles de la carte (lignes et colonnes de la grille), envoyées une fois |
| `GET /api/map/isobars?start&end` | pression au niveau de la mer à 0,5°, jours × lignes × colonnes, dixièmes de hPa ; grille dans les en-têtes |
| `GET /api/map/{grandeur}?start&end` | jours × mailles en entiers 16 bits, dixièmes de l'unité (°C, mm, %) ; -32768 : pas de valeur ; jours, mailles, premier jour et origine dans les en-têtes ; mêmes refus qu'une recherche |
| `GET /api/place?latitude&longitude` | localité la plus proche d'un point (nom, code pays, distance en km), ou trois `null` au-delà de 50 km ; 503 sans `places.tsv` |

Une saison pèse 3,5 Mo, 1,8 Mo compressée (gzip, comme toutes les réponses de plus de 1 ko) ; lecture en 0,02 s, réponse en 0,2 s en local. Contours et icône : `python -m src.store.outlines` (`web/static/geo/europe.json`, 133 ko ; `web/static/icons/europe.svg`, tracé depuis le masque de `map.zarr`).

## 9. Contrôles du 13/10/2026

Après la reconstruction sur E-OBS, contre le serveur local :

- Balayage de 888 lieux (grille de 1,5° × 2,5° et 18 lieux nommés), 797 dans le domaine : aucune erreur, aucune valeur manquante, sur `/api/days`, `/api/normals`, `/api/climate` et `/api/years` (étés 2003 et 2061, hiver 1987). Libellés conformes au masque : E-OBS à Paris, Grenoble, Ajaccio, Tromsø, aux Féroé ; repli ERA5-Land à Rabat, Volgograd, Malte ; ERA5 seul à Lampedusa, à l'île de Sein, en mer.
- Valeur servie égale au fichier corrigé : Paris (48,9 N 2,4 E), Tx du 6/8/2061, 45,91 °C. Paris, 25/7/2019 : 42,3 °C (station de Montsouris 42,6 °C).
- Continuité, moyenne 2015-2025, corrigé − données passées servies : Paris Tx −1,0 K, Tn −0,6 K ; Grenoble Tn −1,1 K ; Chamonix Tx d'hiver −1,5 K ; Ajaccio Tx d'été −2,1 K ; mer d'Azov Tx d'hiver −1,9 K, d'été +1,1 K ; Féroé, Malte, Lampedusa, île de Sein ±0,2 K.
- Temps de réponse : 0,02 à 0,07 s par appel ; carte d'une saison 0,02 s (3,5 Mo), isobares 0,06 s (2 Mo).
- Captures (Playwright) : accueil, documentation, résultats (Paris, Chamonix, Rabat ; 2003 et 2083), cartes (étés 2003, 2019, 2083 avec isobares ; hivers 1987 et 2090) ; aucune erreur JavaScript.

## 10. Tests

`python -m pytest` (198 tests au 13/11/2026, hors `tests/test_grass.py`) : tests Python (API sur un petit stockage construit à la volée par `tests/conftest.py`, règles d'affichage, pages), suite JavaScript (`node --test`, si `node` est installé) et, depuis le 13/11/2026, calculs de la correction (`tests/test_correction.py`, `docs/correction.md` section 12).

## 11. Formulaire : une année ou un type de saison

Depuis le 04/11/2026, l'accueil propose, sous l'étiquette « Période », deux modes après le lieu : « Choisir une année » (une saison et une année ; « Saison entière » jusqu'au 05/11/2026) et « Choisir un type de saison », qui remplace la plage de dates. Les deux écrivent `debut` et `fin`, champs cachés : l'adresse de la page de résultats ne change pas, et une adresse écrite à la main avec d'autres dates fonctionne toujours.

« Type de saison » : une saison, une époque (trois depuis le 05/11/2026, quatre fenêtres de 30 ans le 04/11), un type. À l'envoi, le navigateur demande `/api/kinds`, tire une année au hasard parmi celles du type demandé (`web/static/js/kinds.js`), écrit ses dates et part sur la page de résultats.

| Époque | Années | Source |
|---|---|---|
| Ancien climat | 1970-2010 | données passées (E-OBS pour les températures) |
| Nouveau climat | 2011-2050 | données passées 2011-2025, puis CORDEX corrigé 2027-2050 |
| Climat futur | 2051-2100 | CORDEX corrigé |

- Critère : moyenne de `tasmax` sur les dates de la saison, au lieu (mêmes mailles que la série), valeurs brutes. Chaque époque est classée seule ; sur 40 ou 50 ans, la tendance pèse dans le classement (une saison chaude du climat futur tombe plutôt en fin de siècle) : simplification acceptée le 05/11/2026, le classement sur l'écart à la tendance de l'époque reste possible.
- Le nouveau climat mélange deux sources, et le modèle corrigé est plus frais que les données passées sur 2015-2025 (section 9) : son classement mêle variabilité et cette marche (l'ajustement sur la TRACC est écarté le 13/11/2026 (`docs/choix_modele_cmip6.md`, section 5)). `/api/kinds` lui donne une origine nulle.
- Découpage : les 20 % les plus fraîches, les 60 % du milieu, les 20 % les plus chaudes (`round(0,2 × n)` à chaque bout : 8 sur 41, 10 sur 50).
- Une saison dont les dates sortent d'une période servie est écartée : 2026, l'hiver 2025 (jusqu'en mars 2026), l'hiver 2100.
- Accueil allégé (05/11/2026) : la note « Dates disponibles… Pour les dates futures, la météo affichée n'est pas une prévision, mais une simulation. » ne s'affiche plus en bas de page, mais au survol, au focus ou au toucher du « ? » rond placé après « N'importe quand. » (le même que celui de « Type » ; un astérisque le 05/11 au matin) ; le second paragraphe, devenu « La météo dans le futur est simulée et n'est pas le temps qu'il fera… », et le lien vers la documentation remontent sous le formulaire, en encre claire avec un halo bleu nuit diffus sous les lettres, sans encadré (contraste sous les lettres de 9,3:1 au moins, mesuré sur ordinateur, petit et grand écran, mobile, panneaux ouverts ou fermés).
- La méthode s'affiche derrière un « ? » à côté de « Type » : au survol, au focus clavier ou au toucher, refermée par Échap ou un clic ailleurs (`web/static/js/hint.js`, réutilisable pour les autres notes).
- Libellés : Frais, Normal, Chaud ; en hiver Froid, Normal, Doux. Époque par défaut : nouveau climat ; type par défaut : chaud.
- Records (07/11/2026) : « Record de chaleur » (« Record de douceur » en hiver), la saison de l'époque dont la moyenne des Tx est la plus haute, et « Record de fraîcheur » (« Record de froid » en hiver), la plus basse, même critère que le classement ; menu dans l'ordre de l'échelle, du record froid au record chaud ; puis le jour extrême de la saison : « Jour le plus chaud » au printemps, en été et en automne (la journée de Tx la plus haute de l'époque), « Jour le plus froid » en hiver (la nuit de Tn la plus basse) ; servis par `/api/kinds` (`hottest`, `coldest` : année de la saison, date, valeur ; le plus récent à égalité ; `tasmin` lu en plus de `tasmax`) ; les résultats s'ouvrent sur ce jour (`jour` dans l'adresse, tuile agrandie et cerclée). Lyon : 45,6 °C le 04/08/2100 (climat futur, été), 40,3 °C le 13/08/2003 (ancien climat), -22,5 °C la nuit du 06/01/1971 (ancien climat, hiver, au cœur de six nuits de -12 à -22,5 °C, E-OBS) ; sans tirage, toujours la même année pour un lieu, une saison et une époque (à égalité, la plus récente). Lu dans les `values` de `/api/kinds`, rien de nouveau côté serveur (`web/static/js/kinds.js`, `record`). Lyon, été : 2003 (ancien climat, 30,2 °C), 2050 (nouveau, 30,5 °C), 2085 (futur, 33,1 °C). Champ du type élargi (10rem) : il passe sous la saison et l'époque.
- Époques servies par `/api/config` (`epochs`, `epochs_default`), définies dans `src/app/api/kinds.py`. Choix du projet (04 et 05/11/2026), pas une norme.
- Exemple, Lyon, été, moyenne des Tx : 25,6 °C (ancien climat, 41 étés), 27,6 °C (nouveau, 39), 29,0 °C (futur, 50). Étés chauds du nouveau climat : 2018, 2020, 2022, 2023, 2030, 2041, 2049, 2050 ; frais : 2011, 2013, 2014, 2021, 2028, 2029, 2033, 2039. Réponse en 0,07 s en local.

## 12. Synthèse en tête des résultats

Depuis le 05/11/2026, une carte en tête de la page de résultats (« Été 2063 à Lyon ») donne quelques chiffres des dates affichées, chacun avec sa normale : sa moyenne sur les mêmes dates des années de la période de référence choisie (1991-2020 par défaut), au même lieu, données passées (E-OBS pour les températures, ERA5), mêmes mailles que la série.

| Saison | Chiffres |
|---|---|
| Été | écart de la Tx moyenne ; jours à Tx ≥ 35 °C (« dont N à 40 °C ou plus » s'il y en a) ; nuits tropicales (Tn > 20 °C) ; écart de pluie à la normale en % (« −19 % ») |
| Hiver | écart de la température moyenne ; jours de gel (Tn < 0 °C) ; écart de pluie à la normale en % |
| Printemps, automne | écart de la Tx moyenne ; journées estivales (Tx > 25 °C) ; jours de gel ; écart de pluie à la normale en % |

- Seuils et inégalités de DRIAS (Météo-France, liste des indicateurs du 01/12/2023 : TX35, TR, SD, TNFD) ; 40 °C est un seuil propre au site. Décidé le 05/11/2026.
- Un jour manquant ne compte ni sous ni au-dessus d'un seuil : le comptage est ramené à la longueur de la période, comme la pluie.
- L'écart de température prend l'encre chaude ou froide du graphique au-delà d'un demi-degré.
- La méthode s'affiche derrière un « ? » ; la page de documentation (section « La comparaison aux normales », 06/11/2026) explique la normale d'une date, l'écart du jour et ses couleurs, la synthèse et ses seuils. La tuile agrandie du calendrier donne aussi, dans un petit encadré blanc à droite de la Tx et de la Tn du jour, leur écart à la normale (« +9 °C », arrondi au degré, sur les valeurs non arrondies). Couleur : gris à 0, rouge au-dessus, bleu en dessous, rouge foncé ou bleu foncé à 5 °C d'écart ou plus (seuil DRIAS d'un jour anormalement chaud ou froid, TXND et TNND) ; `gapTone` dans `web/static/js/compare.js`. Tuile agrandie (06/11/2026) : 310 px au moins, chiffres du tableau agrandis (1,19 rem, unités plus petites) ; la ligne de chaleur humide, réservée sur toutes les tuiles d'une période qui en compte, n'y apparaît que pour un jour qui en a, sans hauteur réservée ; le ciel et la chaleur humide dans l'encre de la tuile.
- `GET /api/summary?latitude&longitude&start&end&reference` (`src/app/api/summary.py`) calcule tous les chiffres (`tasmax_mean`, `tas_mean`, `hot_35`, `hot_40`, `tropical_nights`, `summer_days`, `frost_days`, `precipitation`), la page choisit selon la saison (`web/static/js/summary.js`).
- Exemples : Lyon, été 2063 : Tx moyenne 31,2 °C (normale 26,7), 19 jours à 35 °C ou plus (3,2), 38 nuits tropicales (3,5), pluie 73 % de la normale. Grenoble, hiver 2080-2081 : +1,2 °C, 57 jours de gel (57,6).


- Liens de la synthèse (08/11/2026) : trois pastilles côte à côte dans un cadre blanc compact à elles, sous la carte de synthèse et indépendant d'elle (affiché avec les journées) (« Voir cette saison parmi toutes les années », « Voir cette saison sur la carte d'Europe », « Tout comprendre sur les données affichées »), contour bleu sur fond blanc comme le bouton des normales, pleines au survol, pictogrammes grille, carte dépliée, livre ; l'une sous l'autre sous 560 px. Le lien vers la documentation sous la mention « simulation » est retiré : il est dans les pastilles.

## 13. Retouches du 14/11/2026 (revue du site)

- Accueil : la promesse dit « Partout en Europe. N'importe quand. » (« N'importe où » auparavant, faux hors du domaine). Les lieux proposés sous le champ sont ceux du domaine : le navigateur demande dix candidats au géocodage, puis `/api/covered`, et n'en propose que cinq au plus parmi ceux qui sont couverts ; si le nom n'existe qu'ailleurs, « Ce lieu est hors de la zone couverte (Europe). » s'affiche sous le champ, sans attendre l'envoi. Si `/api/covered` ne répond pas, tous les candidats sont proposés et la recherche refuse comme avant.
- Accueil : un lien « Visualisez l'été 2075 à Paris » (un peu plus gros que la note, 1,25rem) sous le formulaire, au-dessus de la phrase « La météo dans le futur est simulée… » (l'été 2063 à Lyon d'abord). Choisi parmi les 74 étés simulés à Paris (maille 48,9 N 2,3 E) : 15 ont un jour à 40 °C ou plus, 5 ont deux épisodes distincts (jours consécutifs à Tx ≥ 35 °C dont un à 40 °C ou plus : 2045, 2073, 2075, 2085, 2093) ; 2075 est le seul dont les deux durent plus d'un jour à 40 °C : 26 et 27 juillet (pic 42,1 °C), puis 8 jours à partir du 24 août dont 5 à 40 °C ou plus (pic 42,3 °C). 6e été le plus chaud en moyenne des Tx (29,3 °C). Le titre ne se coupe plus après un trait d'union (« seront- / ils » sur téléphone) : un caractère de liaison sans largeur (U+2060) suit le trait d'union d'un mot composé (`unbroken`, `web/static/js/prompt.js`).
- Résultats, écran étroit (moins de 60rem) : la liste des journées ne montre que la première semaine ; un bouton « Afficher les 92 journées » la déplie, « Replier les journées » la referme (`foldDays`, `web/static/js/results.js`). Pour l'été 2063 à Lyon sur un téléphone de 390 px, la page passe de 12 400 px à 4 500 px de haut. Un jour demandé par l'adresse (`jour`) déplie la liste et est amené dans la fenêtre. Rien ne change sur un écran large. Le graphique des journées garde sa largeur minimale et défile horizontalement.
- Carte, moins de 1000 px : le titre, les trois menus sur une ligne, la carte, puis le lecteur et la lecture du jour (la carte venait après les réglages et le lecteur). Sur tous les écrans, la note sur les données est repliée sous « Sources et méthode » : à 900 px de haut, le panneau de droite ne déborde plus.

## 14. Partage et phrase d'interprétation (14/11/2026)

Partage (`src/app/api/share.py`, `with_head` dans `src/app/api/app.py`). Les robots qui dessinent l'aperçu d'un lien n'exécutent pas le JavaScript : le serveur écrit donc l'en-tête des quatre pages (titre, description, balises Open Graph, `twitter:card`), à la place du `<title>` du fichier.

- Page de résultats : titre « Été 2075 à Paris · Weather Simulator » (une saison du formulaire est nommée, d'autres dates s'écrivent « Du 1er juillet 2075 au 31 juillet 2075 ») ; description tirée de la synthèse (Tx moyenne et son écart à 1991-2020, jours à 35 °C ou plus, sinon jours de gel), suivie de « Simulation : une météo plausible, pas une prévision. » pour une saison simulée. Exemple : « Été 2075 à Paris : maximales de 29,3 °C en moyenne (+4,5 °C par rapport à 1991-2020), 13 jours à 35 °C ou plus. Simulation : une météo plausible, pas une prévision. »
- Image d'une recherche : `/api/card.png`, 1200 × 630, une tuile par jour dans la couleur de sa Tx (les dix couleurs du calendrier, tenues égales à celles de la feuille de style par un test), une colonne par semaine, lundi en haut, fond clair ; PNG écrit par le serveur avec numpy et zlib, sans bibliothèque d'images ; environ 12 ko, 25 ms.
- Autres pages, et adresse de résultats qui n'est pas une recherche valide : nom du site, promesse, image fixe `web/static/share.png` (le ciel de l'accueil avec sa première question et la promesse, capturé avec Playwright).
- Rien de l'adresse n'est écrit sans échappement ; une adresse refusée par l'API reçoit quand même sa page.
- Les adresses des balises sont absolues et viennent de la requête : derrière un proxy, lancer uvicorn avec `--proxy-headers` pour qu'elles soient en `https`.

Phrase d'interprétation. `/api/summary` renvoie `rank` : parmi les mêmes dates de chaque année observée (1970-2025, l'année montrée exclue si elle est observée), combien ont une moyenne des Tx plus haute, et lesquelles s'il y en a trois au plus (`rank` dans `src/app/api/summary.py`, critère de `kinds.py`). Une saison simulée est ainsi comparée à ce qui a été vécu, pas au modèle. La synthèse l'écrit sous son titre, pour une saison entière du formulaire (`standing`, `web/static/js/summary.js`) :

- aucune année observée plus chaude : « Plus chaud que les 56 étés observés de 1970 à 2025. » (Paris, été 2075) ;
- trois au plus : « Seuls 2 étés observés de 1970 à 2025 ont été plus chauds : 2003, 2023. » (Lyon, été 2030) ;
- moins de la moitié : « Plus doux que 45 des 55 hivers observés de 1970 à 2024. » (Paris, hiver 2080-2081) ;
- la moitié ou plus : « Plus froid que 52 des 54 autres hivers observés de 1970 à 2024. » (Paris, hiver 1985-1986).

Mots du formulaire : chaud et frais, doux et froid en hiver. Le « ? » de la synthèse dit le critère. Limite : le modèle corrigé étant plus frais que les données passées sur 2015-2025 (section 9), le rang d'une saison simulée proche est plutôt sous-estimé.

Type de saison dans l'adresse. Une recherche lancée par « Choisir un type de saison » porte `type` (cool, normal, warm, record, coldRecord, hottestDay, coldestDay) et `epoque` (old, new, future) ; une année choisie à la main ne les porte pas. La synthèse l'écrit sous la phrase de rang : « Un automne chaud du nouveau climat (2011-2050), tiré au hasard. », ou « Record de chaleur du climat futur (2051-2100). » pour un type qui donne toujours la même année. Pour un type tiré au hasard, « Tirer une autre année » redemande `/api/kinds` et ouvre une autre année du même type (`drawAnother`, `web/static/js/kinds.js`) ; le bouton disparaît s'il n'y en a pas d'autre. Des valeurs que le formulaire ne propose pas n'affichent rien.
