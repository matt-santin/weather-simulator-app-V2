# Notes : correction de tas en présence de glace de mer

Notes de travail, état au 26/09/2026. Méthode de base décrite dans `docs/correction.md`.

## Le problème

Le QDM actuel de `tas` échoue là où le modèle a de la banquise qu'ERA5 n'a pas. La table b(τ) apprend un fort réchauffement de la queue froide (jusqu'à +25 K) sur des jours de banquise. Quand le modèle perd sa glace, ce réchauffement s'applique à des jours d'eau libre. Nord de l'Islande (66 N, 20 W), janvier, 2071-2100 : P50 brut −1,0 °C, corrigé +11,6 °C.

## Données réunies

| Donnée | Source | Emplacement (LaCie) |
|---|---|---|
| `sic` CORDEX, 1970-2100 | ESGF (`src/download/esgf.py`) | `cordex/eur11/` (27 fichiers de 5 ans) |
| `sic` remappé à 0,25° | `python -m src.correction.remap sic 1970-2100` | `cordex/eur11_025/` (131 fichiers) |
| `sftlf` CORDEX | ESGF | `cordex/eur11/` |
| `sst`, `istl1` ERA5 journaliers, 1970-2005 | Earth Data Hub (`src/download/era5.py`) | `era5/daily/` |
| `lsm` ERA5 | Earth Data Hub | `era5/fixed/lsm_ERA5.nc` |

`remap.py` lit désormais aussi les fichiers ESGF de 5 ans (fonction `source`).

## Constats

**Marqueur de glace dans ERA5 : `istl1` seul.** Glace si `istl1` ≠ −1,65 °C. Le plancher de `sst` ne voit qu'une partie de la glace (10 à 25 points de moins qu'`istl1`, mailles partiellement englacées) et donne un faux signal sur la Caspienne. `istl1` est défini partout, terre comprise (−1,65 °C) : il faut restreindre aux mailles marines d'ERA5 (`lsm` < 0,5).

**Caspienne : hors sujet.** Elle est hors du domaine corrigé (couverture CORDEX < 90 %). ERA5 n'y a d'ailleurs jamais de glace (plancher de `sst` sans glace). Mer d'Azov : aucune glace, ni dans ERA5 ni dans CORDEX.

**`sic` de CORDEX sur terre n'a pas de sens** : 22 % constants toute l'année à l'est du Ladoga, 100 % de janvier à mai en Laponie. On ne l'utilise que sur les mailles marines d'ERA5.

**Seuil de `sic` : 15 % (décidé).** Là où les saisons de glace concordent (mars-avril, Baltique et mer Blanche), 1 à 15 % retrouvent la fréquence d'ERA5, pas au-delà de 30 %.

**Le modèle se trompe sur la glace elle-même** (% de jours × mailles englacés, `sic` > 15 %) :

| Zone | Source | déc | jan | fév | mars | avr |
|---|---|---|---|---|---|---|
| Golfe de Botnie | ERA5 | 40 | 84 | 97 | 98 | 95 |
| | CORDEX | 0 | 21 | 72 | 89 | 72 |
| Nord Islande | ERA5 | 12 | 16 | 17 | 23 | 21 |
| | CORDEX | 56 | 72 | 80 | 83 | 82 |

Baltique et mer Blanche : glace un à deux mois trop tardive. Nord de l'Islande et Barents : 3 à 5 fois trop de glace.

## Méthodes testées

Principe commun : chaque jour est classé « glace » ou « eau libre » (ERA5 : `istl1`, CORDEX : `sic` > 15 %), et on apprend une table b(τ) par état. Minimum de 50 jours par état et par source sur 1970-2005.

- **Variante B** : chaque état a sa table (b_glace, b_libre) ; si un état a moins de 50 jours d'un côté, ses jours prennent l'ancienne table (tous les jours classés ensemble).
- **Variante C** : jours de glace toujours sur l'ancienne table ; jours d'eau libre sur b_libre.
- **Si b_libre manque** (CORDEX presque toujours englacé sur 1970-2005) : (a) calibration prolongée après 2005 jusqu'à 50 jours d'eau libre, ou (b) b_libre de la maille voisine la plus proche qui en a une. (a) et (b) donnent des résultats proches.

Résultats (C avec b) :

| Maille | Passé vs ERA5 | Futur |
|---|---|---|
| Nord Islande 66 N 20 W, janvier | bon | bon, artefact supprimé |
| Nord Islande 67,25 N 19 W, avril | bon | bon, artefact supprimé |
| Golfe de Botnie 65 N 23 E, février | bon | P50 2021-2050 +2,5 K au-dessus du brut |
| Golfe de Botnie, avril | bon | P95 2071-2100 +3,4 K au-dessus du brut |
| Mer Blanche 64,5 N 38 E, mars | bon | réchauffement 2021-2050 perdu (+2,9 K brut, −0,3 K corrigé) |

## Points non résolus

1. **Échelle** : 496 mailles marines (1 417 mailles-mois) où CORDEX a moins de 50 jours d'eau libre sur 1970-2005, entre l'Islande et le Groenland, en Barents et en mer Blanche. Il y aura pourtant, en médiane, 965 jours d'eau libre CORDEX sur 2006-2100.
2. **État rare non représentatif** : quand un état est rare sur 1970-2005 (par exemple 12 % d'eau libre en mer Blanche), ses jours sont atypiques (hivers doux) et la table apprise sur eux fausse le futur.
3. **ERA5 sans eau libre** (Botnie) : la table empruntée au voisin vient d'un climat différent.
4. **Fréquence de glace** : aucune variante ne corrige la fréquence de glace du modèle, seulement la température par état.

## Proposition en suspens (non validée)

Variante C, avec une règle de représentativité : un état n'a sa propre table que s'il représente au moins 25 % des jours dans ERA5 et dans CORDEX sur 1970-2005 ; sinon, table de la maille voisine la plus proche qui remplit la condition. La juger sur toutes les mailles marines touchées par la glace, avec deux mesures : écart à ERA5 sur 1970-2005 et écart entre réchauffement corrigé et réchauffement brut. Environ 1 h de calcul.

Avant de continuer, il vaut mieux prendre du recul : l'approche par états accumule les cas particuliers. D'autres pistes restent à envisager, par exemple limiter l'écart entre le réchauffement corrigé et le réchauffement brut dans les mailles touchées par la glace.

## Scripts de test

Dans `data/correction/tests_glace/`, à lancer depuis la racine avec `PYTHONPATH=.` :

| Script | Rôle |
|---|---|
| `caspian2.py`, `seas.py` | marqueurs `sst` et `istl1` par zone et par mois |
| `thresholds.py` | fréquence de glace ERA5 contre CORDEX selon le seuil de `sic` |
| `counts.py` | jours de glace et d'eau libre par maille et par mois (sortie `counts.npz`) |
| `iceland.py` | variantes glace/libre et B sur une maille : `iceland.py 66 -20 1` |
| `nolibre.py` | variantes B, (a), (b), C sur une maille : `nolibre.py 67.25 -19.0 4` |
