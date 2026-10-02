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
- La comparaison avec une autre année ne propose que les années ERA5.

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
| `/`, `/resultats`, `/documentation` | les pages |

- Le stockage est ouvert au démarrage ; il vérifie que chaque groupe couvre la période servie.
- Le géocodage (nom vers coordonnées) reste fait par le navigateur, auprès d'Open-Meteo : c'est la seule dépendance extérieure.

| Fichier | Rôle |
|---|---|
| `src/app/store.py` | lecture du stockage, choix des mailles, périodes |
| `src/app/api/validation.py`, `errors.py` | règles de la recherche, refus |
| `src/app/api/pipeline.py`, `contract.py` | du stockage au JSON |
| `src/app/domain/` | règles d'affichage (V1) |
| `web/` | pages, feuille de style, modules JavaScript (V1, adaptés) |

## 5. Tests

`python -m pytest` : tests Python (API sur un petit stockage construit à la volée par `tests/conftest.py`, règles d'affichage, pages) et suite JavaScript (`node --test`, si `node` est installé).
