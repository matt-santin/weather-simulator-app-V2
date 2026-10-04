# Application : stockage de service et site

Le site de la V1 (formulaire, page de résultats, documentation), branché sur les données de la V2. Code dans `src/app/` (serveur) et `web/` (pages), stockage construit par `src/store/build.py`.

## 1. Ce qui est servi

| Période | Source | Origine affichée |
|---|---|---|
| 1970-2025 | ERA5 ; températures : ERA5-Land | réanalyse |
| 2026 | rien : « Données indisponibles » | |
| 2027-2100 | CORDEX corrigé (`docs/correction.md`) | simulation, avec avertissement |

- Une recherche porte sur 92 jours au plus, à l'intérieur d'une seule période. Une plage qui touche 2026, ou qui chevauche 2025 et 2026, est refusée entière.
- Hors du domaine EUR-11 : « Lieu hors de la zone couverte (Europe) ».
- Variables lues : `tasmax`, `tasmin`, `tas`, `pr`, `clt`, `hurs`, `sfcWind`. Règles d'affichage reprises de la V1 (classe de ciel, neige, bandes de température, chaleur humide) ; vent moyen à la place du vent maximal ; température humide calculée à partir de `tas` et `hurs`.
- Comparaison aux normales de saison : voir section 5.

## 2. Deux grilles

| Grandeurs | Grille | Passé | Futur |
|---|---|---|---|
| `tas`, `tasmax`, `tasmin` | 0,1°, terres | ERA5-Land | CORDEX corrigé contre ERA5-Land |
| les autres | 0,25° | ERA5 | CORDEX corrigé contre ERA5 |

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

## 7. Tests

`python -m pytest` : tests Python (API sur un petit stockage construit à la volée par `tests/conftest.py`, règles d'affichage, pages) et suite JavaScript (`node --test`, si `node` est installé).
