# Correction de CORDEX par ERA5

Correction de biais des 14 variables CORDEX (EUR-11, ICHEC-EC-EARTH r12i1p1 / SMHI-RCA4, `historical` puis `rcp_4_5`) contre la réanalyse ERA5, pour 1970-2100. Code dans `src/correction/`.

Chaîne : remappage (`remap.py`), correction par quantiles (`qdm.py`), variables dérivées (`derive.py`), contrôles (`check.py`, `spells.py`, `violin.py`), scores de distribution et de cohérence spatiale (`scores.py`).

## 1. Principe

### Remappage vers la grille ERA5

CORDEX (0,11°, grille en pôle tourné) est ramené sur la grille ERA5 (0,25°). Chaque maille ERA5 prend la moyenne des mailles CORDEX qui la recouvrent, pondérée par la surface de recouvrement. Les mailles ERA5 couvertes à moins de 90 % par le domaine CORDEX sont laissées vides.

`python -m src.correction.remap <variable> 1970-2100`

### Quantile delta mapping (QDM)

Méthode de Cannon et al. (2015), appliquée séparément pour chaque maille et chaque mois calendaire.

**Calibration, une fois pour toutes, sur 1970-2005.** Pour un mois donné (par exemple janvier), on prend tous les jours de ce mois sur 36 ans, soit environ 1 100 jours. On calcule 100 quantiles de la distribution ERA5 (Q_ERA5) et 100 quantiles de la distribution CORDEX (Q_CORDEX).

Q(τ) est la valeur sous laquelle se trouvent une proportion τ des jours. On compare donc des valeurs de quantiles, pas des moyennes.

**Application, pour chaque année de 1970 à 2100.** Pour corriger janvier de l'année Y :

1. on prend la fenêtre de 30 ans Y−15 à Y+14 (bornée à 1970-1999 au début et à 2071-2100 à la fin), en CORDEX brut seulement ;
2. pour chaque jour de janvier Y de valeur x, on calcule son rang τ parmi les janviers CORDEX de cette fenêtre ;
3. on corrige x selon la forme de la variable :
   - additive : x + b(τ), avec b(τ) = Q_ERA5(τ) − Q_CORDEX(τ) ;
   - multiplicative : Q_ERA5(τ) × x / Q_CORDEX(τ), les deux quantiles interpolés séparément, le changement du modèle x / Q_CORDEX(τ) plafonné à 10. Là où Q_CORDEX(τ) = 0 (nuit polaire), x est gardé ;
   - occurrence puis intensité (`pr`) : avant le calcul du rang, les jours sous un seuil propre au modèle, calé pour reproduire la fréquence des jours secs d'ERA5, sont mis à 0 ; les autres reçoivent la forme multiplicative, avec un rang et des quantiles calculés sur les seuls jours de pluie. Détail en section 2.

ERA5 n'intervient que dans la calibration. La fenêtre glissante sert seulement à situer chaque jour dans le climat du modèle à son époque. Un jour de rang 20 % reçoit la même correction en 1987 et en 2080, même s'il est plus chaud en 2080 : l'évolution simulée par le modèle, quantile par quantile, est conservée, comme différence ou comme rapport.

Entre deux quantiles, τ et la correction sont interpolés linéairement. Sous 0,5 % et au-dessus de 99,5 %, on applique la correction du quantile extrême. Valeurs égales (0 % ou 100 % de `clt`, 0 de `rsds`) : rang du milieu de leur groupe. Les valeurs corrigées sont ensuite ramenées dans les bornes physiques de la variable.

`python -m src.correction.qdm <variable>`

Avec `WSA_QDM_TEST=1`, `qdm`, `check`, `spells` et `violin` écrivent et lisent dans `eur11_025_qdm_test/` et `data/correction/test/`, sans toucher aux fichiers définitifs.

## 2. Particularités par variable

Table `VARS` de `src/correction/qdm.py`.

| CORDEX | ERA5 | Conversion | Forme | Bornes |
|---|---|---|---|---|
| `tas`, `tasmax`, `tasmin` | `t2m`, `mx2t`, `mn2t` | aucune | additive | |
| `pr` | `tp` (m/j) | ×1000/86400 | occurrence, puis multiplicative sur les jours de pluie | ≥ 0 |
| `hurs` | `hurs` | aucune | additive | 0 à 100 |
| `clt` | `tcc` (0 à 1) | ×100 | additive | 0 à 100 |
| `sfcWind` | `si10` | aucune | multiplicative | ≥ 0 |
| `rsds` | `ssrd` (J/m², cumul du jour) | /86400 | multiplicative | ≥ 0 |
| `rlds` | `strd` | /86400 | additive | ≥ 0 |
| `ps` | `sp` | aucune | additive | |
| `evspsbl` | `e` (m, négatif pour l'évaporation) | ×(−1000/86400) | additive | |
| `zg500` | `zg500` | aucune | additive | |
| `alb` = `rsus`/`rsds` | (`ssrd` − `ssr`)/`ssrd` | division par max(`rsds`, 1 W/m²) des deux côtés | additive | 0 à 1 |

Tx reste calé sur `mx2t`. Le maximum horaire de `t2m`, plus proche des stations, demanderait un nouveau téléchargement.

### Précipitations : occurrence puis intensité

Adaptation de fréquence de Themeßl et al. (2012), reprise dans xclim/xsdba, puis QDM sur les jours de pluie. Fonctions `calibrate` et `correct` de `qdm.py`, reprises par `check.py` et `violin.py`. Aucun tirage au hasard.

1. Occurrence. Pour chaque maille et chaque mois, sur 1970-2005 : seuil du modèle = valeur qui laisse sous elle la même proportion de jours que la proportion de jours secs (< 1 mm) d'ERA5. Le même seuil sert de 1970 à 2100 : l'évolution du nombre de jours de pluie du modèle est conservée.
2. Sous le seuil, valeur 0. Les jours qui basculent sont choisis selon leur quantité.
3. Intensité : QDM multiplicatif entre les jours du modèle au-dessus du seuil (fenêtre de 30 ans pour le rang) et ceux d'ERA5 ≥ 1 mm, quantiles calculés sans les jours secs.
4. Moins de 30 jours pluvieux sur 1970-2005 dans ERA5 ou dans le modèle, pour une maille et un mois : occurrence corrigée, quantités laissées brutes (juillet : 9 398 mailles, Sahara et Moyen-Orient).
5. Modèle trop sec (plus de jours à 0 exact qu'ERA5 n'a de jours secs, environ 230 mailles désertiques en janvier et juillet) : seuil = plus petite valeur positive. Tous les jours de pluie du modèle sont gardés ; l'occurrence reste trop basse.

La table `pr_quantiles_1970-2005.nc` contient en plus le seuil (`threshold`) et le nombre de jours pluvieux d'ERA5 et du modèle (`n_ref`, `n_hist`).

### Variables dérivées

Calculées après le QDM par `python -m src.correction.derive <étape>` :
- `tn_tx` : `tasmax` et `tasmin` sont corrigés séparément ; les jours où Tn > Tx, les deux valeurs sont échangées. `tas` ne sera pas affiché dans l'application ;
- `huss` : recalculé à partir de `hurs`, `tas` et `ps` corrigés, avec la formule d'ERA5 (Tetens, sur l'eau). Sur ERA5 1970, cette formule appliquée aux moyennes journalières donne +1 % en moyenne et +11,5 % au P99 par rapport au `huss` d'ERA5, calculé heure par heure ;
- `rsus` = `rsds` corrigé × `alb` corrigé, pour que `rsus` ne dépasse jamais `rsds`.

## 3. Exemple : Paris, `tas`, janvier 1970-2005

![Distributions ERA5, CORDEX brut et corrigé, Paris, janvier](../figures/correction/tas_paris_01_violin.png)

- Les moyennes brutes sont presque égales : 3,69 °C pour ERA5, 3,52 °C pour CORDEX. Une correction de la moyenne ajouterait +0,17 K à tous les jours.
- Les formes diffèrent : CORDEX n'a presque pas de queue froide (minimum −8,7 °C contre −12,7 °C). Il est trop chaud de 1,2 K au P5, et trop froid de 0,2 à 0,6 K au-dessus du P25.
- b(τ) refroidit donc les jours froids (jusqu'à −3 K pour le 1 % le plus froid) et réchauffe les autres de 0,2 à 0,6 K.
- Après correction, l'écart à ERA5 est de −0,1 à +0,1 K du P5 au P95. Le minimum corrigé est −11,7 °C, contre −12,7 °C pour ERA5.

L'écart résiduel aux extrêmes a deux causes. D'une part, chaque année est classée dans sa propre fenêtre de 30 ans, pas dans 1970-2005. D'autre part, les quantiles extrêmes reposent sur une dizaine de jours.

Autres figures : `figures/correction/<variable>_paris_{01,07}_violin.png` pour `tasmax`, `tasmin`, `hurs` et `pr`. Pour `pr`, la courbe de droite porte sur le rang parmi les jours de pluie.

`python -m src.correction.violin <variable> 48.86 2.35 <mois> Paris`

## 4. Validation

### Calibration, validation, production de la correction

La méthode est appliquée deux fois, avec les mêmes étapes, sur deux périodes de calibration différentes. On obtient deux tables différentes.

Une table contient, pour chaque maille et chaque mois, les 100 quantiles d'ERA5 et de CORDEX sur la période de calibration, donc la correction de chaque quantile. Exemple, Paris, janvier, `tas`, calibration 1970-2005 : on range les 1 116 jours de janvier de 1970 à 2005 du plus froid au plus chaud, dans ERA5 et dans CORDEX ; au P5, CORDEX est trop chaud de 1,2 K, la table retire donc 1,2 K au P5.

| | Table de production | Table de test |
|---|---|---|
| Calibration | 1970-2005 (36 ans, environ 1 100 jours par mois) | 1970-1987 (18 ans, environ 560 jours par mois) |
| Corrige | 1970-2100 | 1988-2005 |
| Comparée à | rien : pas d'ERA5 après 2005 | ERA5 1988-2005, que la calibration n'a pas vu |
| Enregistrée | `<variable>_quantiles_1970-2005.nc`, fichiers corrigés `eur11_025_qdm/` | non, recalculée en mémoire par `check.py` et `scores.py` |
| Rôle | données de l'application | juger la méthode |

Pourquoi deux tables : sur ses propres années de calibration, la correction reproduit ERA5 par construction (`pr`, janvier 1970-1987, Europe terre : 39,3 % de jours de pluie dans ERA5 et dans le corrigé). Ce résultat ne dit rien des années non vues. La table de test, calibrée sur 1970-1987, est donc jugée sur 1988-2005, qui joue le rôle du futur.

Conséquences :
- les résultats du test sont un peu pessimistes : 18 ans de calibration au lieu de 36, donc plus de bruit d'échantillonnage dans la table ;
- on suppose que la table de production, sur 36 ans, fera au moins aussi bien sur les années futures. Supposition, pas preuve : la table de production n'a jamais été testée sur des années indépendantes. E-OBS, disponible après 2005, permettrait de la tester sur 2006-2024 (proposé, non décidé).

### Contrôles

`python -m src.correction.check <variable>`, sorties dans `data/correction/check_<variable>.log` et `<variable>_validation.png`.

- **Validation croisée.** Calibration sur 1970-1987, correction et comparaison à ERA5 sur 1988-2005 : biais moyen, P5 et P95 par mois, moyenne et RMS entre mailles.
- **Conservation du signal.** Écart 2071-2100 contre 1976-2005, avant et après correction, en différence (forme additive) ou en % (multiplicative).
- **Bornes.** Fréquence des jours secs pour `pr`, part de jours aux bornes pour les variables bornées.
- **Indices** sur 1988-2005, année par année : jours > 25 et > 30 °C, Tx maximal, plus longue série > 30 °C ; nuits tropicales, jours de gel, Tn minimal, plus longue série de gel ; cumul annuel, jours ≥ 1 mm, pluie maximale en 1 et 5 jours, plus longue série sèche, durée moyenne des séries sèches ; persistance jour à jour (corrélation des anomalies au mois) pour toutes les variables.
- **Séries sèches** par saison et par région, 1970-2005 : `python -m src.correction.spells`.

Pour `huss` et `rsus`, dérivées de champs calibrés sur 1970-2005, `check` compare les fichiers finaux à ERA5 sur 1988-2005 : ce n'est pas une validation indépendante.

### Synthèse

Validation croisée, écart au ERA5 sur 1988-2005, moyenne mensuelle ; plage sur les 12 mois.

| Variable | Biais moyen brut | Biais moyen corrigé | RMS entre mailles, brut → corrigé | Signal conservé (moyenne du domaine) |
|---|---|---|---|---|
| `tas` | −1,1 à −2,5 K | −0,6 à +0,2 K | 1,8-3,3 → 0,5-1,7 K | à 0,01 K |
| `tasmax`, `tasmin` | −0,6 à −2,8 K | −0,75 à +0,2 K | | à 0,02 K |
| `hurs` | | +0,5 à +1 % d'avril à septembre | 6-7 → 2-2,8 % | oui |
| `pr` | voir ci-dessous | | | voir ci-dessous |
| `clt` | −4,2 à −7,6 % | −0,3 à +2,5 % | 7,5-13,9 → 3,0-6,5 % | à 0,15 point |
| `sfcWind` | +0,47 à +0,77 m/s | −0,35 à +0,09 m/s | 0,8-1,3 → 0,3-0,7 m/s | à 0,05 point de % |
| `rsds` | +5 à +18 W/m² | −6,8 à −0,3 W/m² | 9-27 → 2-10 W/m² | à 0,3 point de % |
| `rlds` | −5,4 à −10,8 W/m² | −1,0 à +2,7 W/m² | 9-15 → 3,5-8,4 W/m² | à 0,1 W/m² |
| `ps` | −0,9 à +1,4 hPa | −1,2 à +2,2 hPa | 3,6-5,0 → 0,8-6,6 hPa | à 0,02 hPa |
| `evspsbl` | +0,12 à +0,32 mm/j | −0,20 à +0,08 mm/j | 0,4-0,8 → 0,2-0,5 mm/j | à 0,01 mm/j |
| `zg500` | −35 à −56 m | −15 à +16 m | 37-64 → 13-61 m | à 0,5 m |
| `alb` | +0,01 à +0,04 | 0 à +0,01 | 0,04-0,11 → 0,01-0,04 | à 0,01 |
| `huss` (non indépendant) | −0,3 à −1,4 g/kg | −0,01 à +0,16 g/kg | 0,5-1,9 → 0,1-0,3 g/kg | à 1 point de % |
| `rsus` (non indépendant) | +2 à +8 W/m² | −0,25 à +0,24 W/m² | 6-18 → 0,5-2,2 W/m² | à 1 à 3 points de % |

Persistance jour à jour : inchangée par la correction pour toutes les variables. Seule exception notable, sans lien avec la correction : `alb`, 0,56 pour ERA5, 0,75 brut, 0,71 corrigé (section 5).

`ps`, `zg500` : les biais corrigés de février (+2,2 hPa, +16 m) viennent de la variabilité d'ERA5 entre les deux périodes (section 5).

### Scores : distance aux distributions et cohérence spatiale

`python -m src.correction.scores <variable> [lat0 lat1 lon0 lon1]`, sorties dans `data/correction/scores_<variable>.log` et `<variable>_scores.png`. Même validation croisée que `check` ; pour `huss` et `rsus`, fichiers finaux (non indépendant).

**Distance aux distributions.** Pour chaque maille et chaque mois, distance de Wasserstein W1 = moyenne sur τ de |Q_A(τ) − Q_B(τ)| : l'écart moyen entre quantiles de même rang, dans l'unité de la variable. W1 entre ERA5 1988-2005 et, successivement, CORDEX brut et corrigé. Plancher : W1 entre ERA5 1970-1987 et ERA5 1988-2005, soit ce qui sépare déjà deux périodes de 18 ans du climat réel (variabilité et tendance). Une correction calibrée sur 18 ans ajoute son propre bruit d'échantillonnage : un corrigé entre 1 et 1,5 fois le plancher est un bon résultat (estimation, non calculée). Pour `pr`, W1 porte sur les jours ≥ 1 mm, s'il y en a au moins 30 dans chaque échantillon.

Europe terre (35 N et plus, 10 W à 40 E, `lsm` ≥ 0,5, 16 633 mailles), médiane sur les mailles, moyenne des 12 mois :

| Variable | Plancher | Brut | Corrigé | Mailles au plancher, brut → corrigé |
|---|---|---|---|---|
| `tas` | 0,97 K | 2,21 | 0,99 | 17 → 47 % |
| `tasmax` | 1,01 K | 1,72 | 1,09 | 27 → 43 % |
| `tasmin` | 0,90 K | 2,52 | 0,88 | 12 → 49 % |
| `alb` | 0,011 | 0,048 | 0,011 | 8 → 50 % |
| `rsds` | 4,8 W/m² | 20,6 | 6,2 | 6 → 25 % |
| `rlds` | 3,8 W/m² | 13,5 | 4,9 | 3 → 31 % |
| `sfcWind` | 0,13 m/s | 0,71 | 0,18 | 11 → 26 % |
| `evspsbl` | 0,08 mm/j | 0,28 | 0,10 | 14 → 34 % |
| `clt` | 3,0 % | 10,5 | 4,0 | 9 → 25 % |
| `hurs` | 1,4 % | 4,6 | 1,9 | 11 → 30 % |
| `zg500` | 21 m | 39 | 27 | 21 → 36 % |
| `ps` | 1,5 hPa | 2,3 | 1,9 | 29 → 28 % |
| `pr`, jours de pluie | 0,50 mm/j | 0,74 | 0,73 | 29 → 20 % |
| `huss` (non indépendant) | 0,25 g/kg | 0,59 | 0,22 | 20 → 59 % |
| `rsus` (non indépendant) | 1,2 W/m² | 7,8 | 0,9 | 4 → 71 % |

- Sauf `ps`, `zg500` et `pr`, la correction ramène W1 près du plancher, dans toutes les régions (Europe mer, nord de 60 N, sud de 35 N) ; au sud de 35 N, le corrigé passe souvent sous le plancher, ERA5 y variant peu d'une période à l'autre.
- `ps`, `zg500` : bons en été (`zg500`, juin : brut 54 m, corrigé 17 m, plancher 13 m), dégradés en hiver (section 5).
- `pr` : pas de gain sur l'intensité en moyenne sur l'Europe (section 5). Fréquence des jours de pluie, écart absolu médian à ERA5, Europe terre : janvier plancher 5,2, brut 7,3, corrigé 6,3 points ; octobre 2,5, 4,5, 3,8.

**Cohérence spatiale.** Chaque maille est corrigée seule : la correction pourrait rendre deux voisines moins semblables un jour donné. Anomalies journalières (à la moyenne de chaque maille et de chaque mois), corrélées dans le temps entre chaque maille et ses voisines à 1, 2, 4 et 8 mailles (28 à 220 km), vers l'est et vers le nord, par saison. Pour `pr`, en plus, l'occurrence des jours de pluie.

- La correction ne dégrade la cohérence pour aucune variable : brut et corrigé à ±0,02. Exceptions : `pr` au sud de 35 N au printemps, à 8 mailles, 0,42 brut, 0,34 corrigé ; `alb` en été, 0,34 et 0,29.
- Les écarts à ERA5 viennent du modèle. Exemples à 8 mailles, Europe terre : `pr` en hiver, ERA5 0,72, brut 0,61, corrigé 0,60 ; `tasmin` en été, 0,86, 0,70, 0,71 ; `alb` en été, 0,54, 0,34, 0,29. ERA5, de résolution effective plus grossière, est probablement plus lisse que le modèle, ce qui explique une partie de ces écarts.

### Températures

| Indice, 1988-2005, moyenne sur le domaine | ERA5 | brut | corrigé | RMS entre mailles, brut → corrigé |
|---|---|---|---|---|
| jours Tx > 30 °C par an | 20,0 | 17,9 | 18,7 | 8,9 → 3,6 |
| plus longue série Tx > 30 °C (j) | 12,7 | 10,5 | 11,8 | 8,5 → 3,5 |
| nuits tropicales par an | 26,5 | 14,5 | 24,5 | 24,7 → 4,8 |
| jours de gel par an | 73,0 | 90,0 | 73,2 | 26,0 → 6,1 |
| persistance jour à jour (Tx) | 0,75 | 0,76 | 0,75 | inchangée |

Signal : au P95, écart brut/corrigé jusqu'à 7,9 K en hiver, dans les mailles de neige et de glace (section 5).

### Précipitations

| Indice, 1988-2005 | ERA5 | brut | corrigé | RMS entre mailles, brut → corrigé |
|---|---|---|---|---|
| cumul annuel (mm) | 779 | 827 | 774 | 201 → 73 |
| jours ≥ 1 mm par an | 140,4 | 141,9 | 142,9 | 21,5 → 7,5 |
| plus longue série sèche (j) | 47,0 | 38,0 | 47,3 | 31,8 → 9,9 |
| durée moyenne des séries sèches (j) | 12,4 | 7,3 | 14,4 | 20,6 → 12,9 |

- Durée moyenne des séries sèches, médiane sur les mailles, Europe terre : ERA5 3,2 à 3,7 j selon la saison, corrigé 3,0 à 3,6 j. L'écart sur le domaine vient des déserts (section 5).
- Signal, juin : 824 mailles dont le signal est décalé de plus de 10 points, 7 de plus de 20. Alpes maritimes (44,5 N 7,25 E) : brut +51 %, corrigé +79 %. Nord-est de la Turquie (40,5 N 41,25 E) : +43 %, +75 %.
- Jours qui basculent (1970-2005) : environ 6 % des jours en médiane, 16 à 17 % au P95 des mailles. Ce sont des jours gris : en juillet, anomalie d'humidité brute de +2,9 à +3,5 % et d'amplitude Tx − Tn de −0,4 à −0,6 K, entre les jours secs (−2,3 %, +0,3 K) et les jours pluvieux (+4,8 %, −0,7 K).
- Jours de pluie corrigés sous 1 mm : 0,1 à 0,2 % des jours de pluie. Pas de plancher.

Sorties : `check_pr.log`, `pr_spells.log`, `pr_analyse.log` (signal en montagne, jours qui basculent, mailles sèches), `pr_series_seches.log`.

## 5. Défauts connus

### Neige et glace (`tas`, `tasmax`, `tasmin`) : à traiter

Dans une partie des mailles, le modèle a une surface qu'ERA5 n'a pas, ou pas au même moment : banquise (nord de l'Islande, Barents, Botnie, mer Blanche), neige (Scandinavie, Russie du Nord, Alpes, Caucase). Les jours froids de CORDEX y sont trop froids de 15 à 25 K, alors que les jours chauds sont presque justes. La table b(τ) réchauffe alors fortement la queue froide. Quand le modèle perd cette glace ou cette neige dans le futur, cette correction s'applique à des jours qui ne sont plus sur de la glace ou de la neige.

Exemple, nord de l'Islande (66 N, 20 W), janvier, 2071-2100 contre 1976-2005 : P50 +6,8 K brut, +6,3 K corrigé ; P95 +2,5 K brut, +5,9 K corrigé. La table passe de +25 K pour les jours les plus froids à +3 K pour les jours médians, plus vite que la température du modèle ne monte : l'ordre des jours s'inverse (corrélation de rang brut/corrigé −0,43), et 24 % des jours de janvier 2071-2100 corrigés dépassent le maximum de janvier d'ERA5 (7,0 °C). Le 13/01/2080, −12,9 °C brut devient +10,7 °C.

![Nord de l'Islande, janvier, 2071-2100](../figures/correction/tas_islande-nord_01_futur_violin.png)

Étendue : 6 247 mailles sur 53 573 ont, au moins un mois, un biais au P5 de plus de 10 K qui dépasse de plus de 7 K celui du P95 (seuils arbitraires). 1 393 en mer, 543 sur les côtes (`lsm` de 0,5 à 0,9), 4 311 sur terre, surtout en Russie du Nord (2 729) et en Scandinavie (1 517). Le problème est donc surtout celui de la neige sur terre.

C'est le défaut le plus gênant : il touche la zone d'intérêt et l'information principale. Pour l'instant, on garde le QDM et on marque ces mailles par l'indicateur de fiabilité (section 7). Essais sur la glace de mer : `docs/notes_correction_glace.md`.

### Déserts (`pr`) : accepté

L'écart sur la durée moyenne des séries sèches (14,4 j contre 12,4) vient entièrement des mailles à moins de 20 jours de pluie par an (sud de 35 N). Ailleurs, l'écart médian est de −0,2 j (Europe terre : 4,0 j contre 4,2). En validation croisée, le seuil y repose sur 4 ou 5 jours du modèle en 18 ans : à 26 N 0,25 E, ERA5 a 3 jours de pluie par an, le corrigé 0,2. Sur le calage complet : 0,40 % de jours de pluie en juillet contre 0,47 % ; 0,78 % en janvier contre 1,71 %. Dans les mailles à quantités brutes, un jour de pluie de juillet apporte 5,7 mm contre 2,9 mm dans ERA5, pour une moyenne mensuelle juste (0,03 mm/j).

Accepté : ERA5 est peu fiable dans ces déserts, situés en bordure du domaine. Ces mailles seront signalées par l'indicateur de fiabilité (critère immédiat : `n_ref` ou `n_hist` < 30).

### Amplification du signal de `pr` en montagne : accepté

Le signal relatif corrigé reste plus fort que le brut là où ERA5 est bien plus pluvieux que le modèle : Alpes maritimes en juin, +79 % contre +51 %. La version 2 donnait +154 % (section 6).

### Jours à 100 % de `clt` : à surveiller

La forme additive pousse les journées très couvertes au-delà de 100 %, ramenées à la borne. Part des jours à 100 % en validation croisée : ERA5 1,3 à 3,1 % selon le mois ; brut 0,0 à 0,2 % ; corrigé 4 à 10,3 % d'octobre à mars (maximum en janvier), 2,4 à 4,9 % d'avril à septembre. Biais moyen corrigé de +1 à +2,5 % en hiver. Piste possible, non décidée : forme multiplicative sur 100 − `clt`, ou correction par quantiles bornée.

### Non-stationnarité du biais : `rsds`, `hurs`

En validation croisée, `rsds` corrigé reste trop sombre de 4 à 7 W/m² d'avril à août : ERA5 s'éclaircit entre 1970-1987 et 1988-2005 par rapport au modèle. Explication probable, à vérifier : la baisse des aérosols en Europe (éclaircissement), que RCA4, à aérosols constants, ne représente pas (Boé et al. 2020, Schumacher et al. 2024). Le même mécanisme sous-estime le réchauffement estival du modèle, de 1,5 à 2 K en fin de siècle en RCP8.5 selon Boé et al. La correction ne peut pas le rattraper : elle conserve le signal du modèle.

`hurs` : biais résiduel de +0,5 à +1 % d'avril à septembre, ERA5 s'asséchant sur terre entre les deux périodes, pas le modèle.

### `ps` et `zg500` en hiver : à décider

En validation croisée, la correction dégrade `ps` et `zg500` en hiver. `zg500`, Europe terre, W1 : février brut 35 m, corrigé 45 m, plancher 39 m ; mars 29, 45, 29 ; décembre 18, 28, 16. `ps`, février : 2,9, 3,8, 4,0 hPa. Ce sont les mois au plancher le plus haut : la circulation d'hiver d'ERA5 change entre 1970-1987 et 1988-2005 (probablement la phase positive de l'oscillation nord-atlantique de la fin des années 1980 et du début des années 1990, non vérifié). Le brut y est déjà au niveau du plancher ; la correction prend l'état de la circulation d'ERA5 en 1970-1987 pour un biais du modèle. Sur 1970-2005, la calibration définitive porte sur 36 ans et le défaut est probablement plus faible, mais de même nature.

Options, non décidées : garder la correction toute l'année ; la limiter aux mois où le biais brut dépasse nettement le plancher ; corriger seulement la moyenne. Ces variables servent peu à l'affichage.

### Intensité de `pr` : pas de gain en moyenne, bruit de calibration

W1 sur les jours de pluie, Europe terre : le corrigé fait moins bien que le brut en hiver (janvier : plancher 0,47, brut 0,50, corrigé 0,61 mm/j), mieux en fin de printemps et en été (mai : 0,48, 0,95, 0,71). Le gain de la correction de `pr` vient de la fréquence des jours de pluie et de certaines zones (boîte 44-48 N, 4-10 E, janvier : 0,65, 1,46, 0,86). Cause vérifiée : le bruit d'échantillonnage de la calibration (environ 280 jours de pluie par maille sur 18 ans pour 100 quantiles). Mailles d'Europe terre classées selon l'intensité moyenne des jours de pluie du brut, rapportée à ERA5 1988-2005 ; W1 rapporté au plancher, médiane :

| Mois | Brut juste (0,9 à 1,1) : brut → corrigé | Brut biaisé (hors 0,9 à 1,1) : brut → corrigé |
|---|---|---|
| janvier | 8 852 mailles, 0,80 → 1,29 | 7 781 mailles, 1,5 à 2,0 → 1,15 à 1,50 |
| avril | 6 358, 0,94 → 1,38 | 10 275, 1,6 à 2,3 → 1,4 à 1,6 |
| juillet | 5 585, 1,07 → 1,51 | 9 734, 2,2 → 1,5 à 1,6 |
| octobre | 7 443, 1,02 → 1,47 | 9 138, 1,6 à 2,1 → 1,5 à 1,7 |

Le corrigé se place vers 1,3 à 1,6 fois le plancher quel que soit le brut : il améliore les mailles biaisées (61 à 74 % des mailles améliorées) et dégrade les mailles justes (16 à 24 % améliorées). Le 9e décile passe de 3,0-3,8 à 2,4-3,1 fois le plancher, la part des mailles au-delà de 2 fois le plancher de 21-40 % à 18-30 %. Janvier : Russie et Ukraine, brut juste (0,70 fois le plancher), corrigé 1,42 ; Alpes, 1,59 et 1,21. Script : `pr_mailles.py` (bloc-notes, non versionné).

La calibration définitive porte sur 36 ans, deux fois plus de jours : le bruit y est plus faible que dans ce test. Pistes, non décidées : calibrer chaque mois avec les mois voisins (fenêtre de 3 mois, trois fois plus de jours), réduire le nombre de quantiles, ne corriger l'intensité que là où le biais dépasse le bruit. Les autres variables sont probablement concernées dans une moindre mesure (`hurs`, `clt` : corrigé à 1,3 fois le plancher). Cartes : `pr_scores.png`.

### Bruine de `pr` supprimée : moyenne trop basse, à décider

Les jours sous le seuil sont mis à 0 ; la bruine d'ERA5 (jours de 0 à 1 mm) n'est pas compensée. Europe terre, 1970-1987 (période de calibration de la table de test) :

| | Pluie moyenne (mm/j) | Jours ≥ 1 mm | Pluie par jour de pluie (mm) | Apport de la bruine (mm/j) |
|---|---|---|---|---|
| ERA5, janvier | 2,11 | 39,3 % | 4,88 | 0,14 |
| corrigé, janvier | 1,97 | 39,3 % | 4,89 | 0 |
| ERA5, juillet | 2,52 | 39,4 % | 5,77 | 0,11 |
| corrigé, juillet | 2,40 | 39,2 % | 5,84 | 0 |

Moyenne corrigée trop basse de 6,5 % en janvier, 4,5 % en juillet. Sur 1988-2005, le corrigé est au contraire trop pluvieux (janvier +13 %, juillet +4 %) : il garde l'évolution du modèle, qui gagne des jours de pluie quand ERA5 en perd.

Options : (1) multiplier les jours de pluie par le rapport cumul total / cumul des jours ≥ 1 mm d'ERA5, par maille et par mois ; (2) seuil à 0,1 mm, au risque de reproduire la bruine excessive des réanalyses (51 % des jours de janvier dans ERA5) ; (3) accepter. Script : `pr_signe.py` (bloc-notes, non versionné).

### Persistance de `alb`

Corrélation d'un jour au suivant : ERA5 0,56, brut 0,75, corrigé 0,71. La surface du modèle varie moins d'un jour à l'autre que celle d'ERA5 ; la correction, qui agit sur les distributions, n'y change presque rien.

### Échange Tn/Tx

Le brut n'a aucun jour Tn > Tx ; la correction séparée en crée. 21 millions de valeurs échangées sur 1970-2100, de 0,4 % des jours-mailles au début à 1,1 % en 2100. En 1990 : écart médian 0,4 K, P99 4,4 K. Surtout dans les mailles mixtes terre-mer (îles de l'Égée, cap Corse, Minorque : jusqu'à 24 % des jours). Même phénomène observé dans la V1 avec la correction d'Open-Meteo.

### Signal de `rsds` et `rsus` en % dans la nuit polaire

En janvier et décembre, l'écart maximal brut/corrigé du signal relatif atteint des centaines, voire des milliers de % (`rsus` : 9 192 % en décembre), sur des mailles où le rayonnement est presque nul. Artefact du pourcentage sur des valeurs proches de 0, sans conséquence.

## 6. Essais non retenus

### `pr`, versions 1 et 2

1. Méthode de Cannon (2015) : valeurs sous 1 mm/j remplacées par des tirages au hasard entre 0 et 1 mm, rapport plafonné à 10, valeurs corrigées sous 1 mm mises à 0. Cumul annuel et jours de pluie corrigés, mais séries sèches raccourcies de 5 à 10 % partout : les jours secs à rendre pluvieux sont choisis au hasard et coupent les séries.
2. Tirages sur les zéros seulement, bruine gardée. Séries sèches réparées, mais signal amplifié en montagne : Alpes maritimes, juin, brut +51 %, corrigé +154 % ; 1 793 mailles décalées de plus de 10 points en juin, 65 de plus de 20. Cause : à un rang où le modèle passé n'a que de la bruine (0,1 mm) et ERA5 déjà 5 mm, un futur à 1,5 mm donne un changement de 15, plafonné à 10, soit 50 mm.

Un plancher sur le dénominateur a été envisagé, puis écarté. Comparaison des versions 2 et 3 :

| Indice, 1988-2005 | ERA5 | version 2 | version 3 (retenue) |
|---|---|---|---|
| cumul annuel (mm), RMS entre mailles | | 92 | 73 |
| jours ≥ 1 mm par an, RMS | | 11,6 | 7,5 |
| plus longue série sèche (j) | 47,0 | 45,2 | 47,3 |
| durée moyenne des séries sèches (j) | 12,4 | 11,8 | 14,4 |
| mailles décalées de plus de 10 / 20 points, juin | | 1 793 / 65 | 824 / 7 |

Sorties de la version 2 : `*_v2` dans `data/correction/`.

### Correction multivariée (MBCn)

MBCn (Cannon 2018) corrige plusieurs variables ensemble : QDM univarié de chaque variable, puis réordonnancement des jours pour reproduire les liens entre variables d'ERA5. Essai sur 5 mailles (Paris, Grenoble, Alpes 46,5 N 8 E, nord de l'Islande, Botnie), 6 variables : `tas`, amplitude diurne (`tasmax − tasmin`, avec `mx2t − mn2t` pour ERA5), `pr`, `hurs`, `sfcWind`, `rsds`. Réordonnancement à l'intérieur de chaque mois de chaque année, pour garder exactement la distribution univariée de l'année.

- Distributions et réchauffement : identiques à l'univarié, par construction.
- Liens entre variables (écart moyen des corrélations de rang à ERA5 sur 7 paires, validation croisée 1988-2005) : meilleurs dans 8 cas maille-saison sur 10, égaux dans 1, moins bons dans 1 (Paris en été). Gain le plus net aux Alpes en été (0,42 à 0,12).
- Persistance : l'autocorrélation de `tas` d'un jour au suivant baisse, jusqu'à 0,1 (Alpes en hiver : 0,69 à 0,59, ERA5 0,79). Le lien pluie/rayonnement s'affaiblit (Paris en été : −0,69 ERA5, −0,62 univarié, −0,42 MBCn).
- Coût : 0,14 s par transformation N-pdf, soit environ 140 jours de calcul sur un cœur pour le domaine avec le script d'essai ; à réduire par vectorisation et pas de 10 ans, non mesuré.
- Aux Alpes, en été, CORDEX brut est à 0 °C contre 8,3 °C pour ERA5, et le lien température/rayonnement a le mauvais signe : signature probable d'une surface enneigée, à confirmer.

Pas de décision prise. Scripts : `data/correction/tests_mbcn/` (non versionnés).

### Validation par tirage d'années au hasard

18 ans de calibration, 18 de validation, tirage répété, en plus du découpage chronologique : proposée, non retenue pour le moment.

## 7. Points ouverts

**Indicateur de fiabilité.** Le QDM transforme chaque jour par la courbe x → x + b(τ(x)). L'ordre des jours est respecté tant que cette courbe monte. On retient sa pente minimale, mesurée entre déciles pour ne pas réagir aux irrégularités de b(τ), pour chaque maille, chaque mois et chaque année (la fenêtre glissante change d'une année à l'autre).

| Pente minimale | Signification |
|---|---|
| ≈ 1 | correction douce |
| entre 0 et 1 | jours comprimés |
| < 0 | ordre des jours inversé (nord de l'Islande, janvier 2071-2100) |

Classes proposées, seuils à fixer : vert au-dessus de 0,5, orange de 0 à 0,5, rouge sous 0. Calcul à partir des tables de quantiles et des quantiles de chaque fenêtre, sans relire les séries journalières ; environ 84 Mo en classes. Première étape : cartes de la pente minimale par mois, pour 1976-2005 et 2071-2100, pour choisir les seuils. Pour `pr`, s'ajoutent les mailles-mois à moins de 30 jours de pluie. Usage dans l'application (masquage ou avertissement) à décider avec l'interface.

**Domaine Afrique.** Le Sahara sera au centre du domaine : le défaut des déserts (section 5) est à reprendre, par exemple avec un seuil calé sur plusieurs mois voisins.

**Bornes de `clt`.** Voir section 5.

**Reportés.** Le masque mer ; la vérification Tn < Tx au moment de servir une météo (filet de sécurité dans le back-end).

## 8. État

Au 28/09/2026 : les 14 variables et `alb` sont corrigées et contrôlées (`check` et `scores`). Restent les décisions de la section 5 (`ps` et `zg500` en hiver, intensité de `pr`, neige et glace).

Longs calculs à lancer sous `caffeinate`, chargeur branché : sur batterie, le Mac se met en veille profonde, ce qui suspend le calcul et peut provoquer un message de disque mal éjecté. Durées observées : remappage 8 min par variable, QDM 32 à 43 min, `check` 4 à 8 min, `scores` 2 à 5 min.

## Fichiers

| Fichier | Contenu |
|---|---|
| `data/correction/poids_eur11_era5.npz` | poids du remappage CORDEX vers ERA5 |
| `data/correction/<variable>_quantiles_1970-2005.nc` | quantiles ERA5 et CORDEX par mois et par maille ; pour `pr`, seuil et nombre de jours de pluie |
| `data/correction/remap.log`, `qdm_<variable>.log`, `derive_<étape>.log` | journaux des calculs |
| `data/correction/check_<variable>.log`, `<variable>_validation.png` | contrôles |
| `data/correction/scores_<variable>.log`, `<variable>_scores.png` | distance aux distributions (W1) et cohérence spatiale |
| `data/correction/pr_spells.log`, `pr_spells.png`, `pr_analyse.log`, `pr_series_seches.log` | contrôles propres à `pr` ; `*_v2` : version 2 |
| `figures/correction/` | figures de distribution (`violin.py`) |
| `LaCie/.../cordex/eur11_025/` | CORDEX remappé à 0,25°, brut |
| `LaCie/.../cordex/eur11_025_qdm/` | CORDEX remappé à 0,25°, corrigé |
