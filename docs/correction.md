# Correction de CORDEX par ERA5

Méthode appliquée à `tas` (température moyenne journalière à 2 m). Code dans `src/correction/`.

## 1. Remappage vers la grille ERA5

CORDEX (EUR-11, 0,11°, grille en pôle tourné) est ramené sur la grille ERA5 (0,25°). Chaque maille ERA5 prend la moyenne des mailles CORDEX qui la recouvrent, pondérée par la surface de recouvrement. Les mailles ERA5 couvertes à moins de 90 % par le domaine CORDEX sont laissées vides.

`python -m src.correction.remap tas 1970-2100`

## 2. Quantile delta mapping (QDM)

Méthode de Cannon et al. (2015), forme additive, appliquée séparément pour chaque maille et chaque mois calendaire.

**Calibration, une fois pour toutes, sur 1970-2005.** Pour un mois donné (par exemple janvier), on prend tous les jours de ce mois sur 36 ans, soit environ 1 100 jours. On calcule 100 quantiles de la distribution ERA5 (Q_ERA5) et 100 quantiles de la distribution CORDEX (Q_CORDEX). La correction est la différence des deux pour chaque rang τ :

b(τ) = Q_ERA5(τ) − Q_CORDEX(τ)

Q(τ) est la température sous laquelle se trouvent une proportion τ des jours. b(τ) compare donc des valeurs de quantiles, pas des moyennes.

**Application, pour chaque année de 1970 à 2100.** Pour corriger janvier de l'année Y :

1. on prend la fenêtre de 30 ans Y−15 à Y+14 (bornée à 1970-1999 au début et à 2071-2100 à la fin), en CORDEX seulement ;
2. pour chaque jour de janvier Y de valeur x, on calcule son rang τ parmi les janviers CORDEX de cette fenêtre ;
3. la valeur corrigée est x + b(τ).

La fenêtre est toujours lue brute. Une première version du script la lisait dans le tableau qu'il corrigeait au fur et à mesure : pour une année Y, les années de la fenêtre antérieures à Y étaient déjà corrigées. Corrigé le 26/09/2026, fichiers régénérés.

ERA5 n'intervient que dans la calibration. La fenêtre glissante sert seulement à situer chaque jour dans le climat du modèle à son époque. Un jour de rang 20 % reçoit la même correction b(20 %) en 1987 et en 2080, même s'il est plus chaud en 2080 : le réchauffement simulé par le modèle, quantile par quantile, est conservé.

Entre deux quantiles, τ et b sont interpolés linéairement. Sous 0,5 % et au-dessus de 99,5 %, on applique la correction du quantile extrême.

`python -m src.correction.qdm tas`

## 3. Exemple : Paris, janvier 1970-2005

![Distributions ERA5, CORDEX brut et corrigé, Paris, janvier](../figures/correction/tas_paris_01_violin.png)

- Les moyennes brutes sont presque égales : 3,69 °C pour ERA5, 3,52 °C pour CORDEX. Une correction de la moyenne ajouterait +0,17 K à tous les jours.
- Les formes diffèrent : CORDEX n'a presque pas de queue froide (minimum −8,7 °C contre −12,7 °C). Il est trop chaud de 1,2 K au P5, et trop froid de 0,2 à 0,6 K au-dessus du P25.
- b(τ) refroidit donc les jours froids (jusqu'à −3 K pour le 1 % le plus froid) et réchauffe les autres de 0,2 à 0,6 K.
- Après correction, l'écart à ERA5 est de −0,1 à +0,1 K du P5 au P95. Le minimum corrigé est −11,7 °C, contre −12,7 °C pour ERA5.

L'écart résiduel aux extrêmes a deux causes. D'une part, chaque année est classée dans sa propre fenêtre de 30 ans, pas dans 1970-2005. D'autre part, les quantiles extrêmes reposent sur une dizaine de jours.

`python -m src.correction.violin tas 48.86 2.35 1 Paris`

## 4. Validation

`python -m src.correction.check tas`

**Validation croisée.** On calibre sur 1970-1987, puis on corrige et on compare à ERA5 sur 1988-2005. Le biais moyen passe de −1,1 à −2,5 K à une valeur entre −0,6 et +0,2 K, selon le mois. L'erreur quadratique entre mailles passe de 1,8 à 3,3 K à 0,5 à 1,7 K.

**Conservation du signal.** On compare l'écart entre 2071-2100 et 1976-2005, avant et après correction. En moyenne sur le domaine, il est conservé à 0,01 K près tous les mois. Maille par maille, l'écart sur la moyenne reste sous 0,9 K ; sur le P95, il atteint 7,9 K en hiver, dans les mailles décrites ci-dessous.

**Limite identifiée.** Dans une partie des mailles, le modèle a une surface qu'ERA5 n'a pas, ou pas au même moment : banquise (nord de l'Islande, Barents, Botnie, mer Blanche), neige (Scandinavie, Russie du Nord, Alpes, Caucase). Les jours froids de CORDEX y sont trop froids de 15 à 25 K, alors que les jours chauds sont presque justes. La table b(τ) réchauffe alors fortement la queue froide. Quand le modèle perd cette glace ou cette neige dans le futur, cette correction s'applique à des jours qui ne sont plus sur de la glace ou de la neige.

Exemple, nord de l'Islande (66 N, 20 W), janvier, 2071-2100 contre 1976-2005 : P50 +6,8 K brut, +6,3 K corrigé ; P95 +2,5 K brut, +5,9 K corrigé. La table passe de +25 K pour les jours les plus froids à +3 K pour les jours médians, plus vite que la température du modèle ne monte : l'ordre des jours s'inverse (corrélation de rang brut/corrigé −0,43), et 24 % des jours de janvier 2071-2100 corrigés dépassent le maximum de janvier d'ERA5 (7,0 °C). Le 13/01/2080, −12,9 °C brut devient +10,7 °C.

![Nord de l'Islande, janvier, 2071-2100](../figures/correction/tas_islande-nord_01_futur_violin.png)

Étendue : 6 247 mailles sur 53 573 ont, au moins un mois, un biais au P5 de plus de 10 K qui dépasse de plus de 7 K celui du P95 (seuils arbitraires). 1 393 en mer, 543 sur les côtes (`lsm` de 0,5 à 0,9), 4 311 sur terre, surtout en Russie du Nord (2 729) et en Scandinavie (1 517). Le problème est donc surtout celui de la neige sur terre.

Piste retenue pour l'instant : garder le QDM, marquer ces mailles par un indicateur de fiabilité et les masquer ou les signaler dans l'application. Le traitement de fond est reporté. Essais sur la glace de mer : `docs/notes_correction_glace.md`.

**Indicateur de fiabilité (à faire).** Le QDM transforme chaque jour par la courbe x → x + b(τ(x)). L'ordre des jours est respecté tant que cette courbe monte. On retient sa pente minimale, mesurée entre déciles pour ne pas réagir aux irrégularités de b(τ), pour chaque maille, chaque mois et chaque année (la fenêtre glissante change d'une année à l'autre).

| Pente minimale | Signification |
|---|---|
| ≈ 1 | correction douce |
| entre 0 et 1 | jours comprimés |
| < 0 | ordre des jours inversé (nord de l'Islande, janvier 2071-2100) |

Classes proposées, seuils à fixer : vert au-dessus de 0,5, orange de 0 à 0,5, rouge sous 0. Calcul à partir des tables de quantiles et des quantiles de chaque fenêtre, sans relire les séries journalières ; environ 84 Mo en classes. Première étape : cartes de la pente minimale par mois, pour 1976-2005 et 2071-2100, pour choisir les seuils. Usage dans l'application (masquage ou avertissement) à décider avec l'interface.

## 5. Correction multivariée (MBCn) : essai

MBCn (Cannon 2018) corrige plusieurs variables ensemble : QDM univarié de chaque variable, puis réordonnancement des jours pour reproduire les liens entre variables d'ERA5. Essai sur 5 mailles (Paris, Grenoble, Alpes 46,5 N 8 E, nord de l'Islande, Botnie), 6 variables : `tas`, amplitude diurne (`tasmax − tasmin`, avec `mx2t − mn2t` pour ERA5), `pr`, `hurs`, `sfcWind`, `rsds`. Réordonnancement à l'intérieur de chaque mois de chaque année, pour garder exactement la distribution univariée de l'année.

- Distributions et réchauffement : identiques à l'univarié, par construction.
- Liens entre variables (écart moyen des corrélations de rang à ERA5 sur 7 paires, validation croisée 1988-2005) : meilleurs dans 8 cas maille-saison sur 10, égaux dans 1, moins bons dans 1 (Paris en été). Gain le plus net aux Alpes en été (0,42 à 0,12).
- Persistance : l'autocorrélation de `tas` d'un jour au suivant baisse, jusqu'à 0,1 (Alpes en hiver : 0,69 à 0,59, ERA5 0,79). Le lien pluie/rayonnement s'affaiblit (Paris en été : −0,69 ERA5, −0,62 univarié, −0,42 MBCn).
- Coût : 0,14 s par transformation N-pdf, soit environ 140 jours de calcul sur un cœur pour le domaine avec le script d'essai ; à réduire par vectorisation et pas de 10 ans, non mesuré.
- Aux Alpes, en été, CORDEX brut est à 0 °C contre 8,3 °C pour ERA5, et le lien température/rayonnement a le mauvais signe : signature probable d'une surface enneigée, à confirmer.

Pas de décision prise. Scripts : `data/correction/tests_mbcn/` (non versionnés).

## 6. Autres variables

### Choix

Même QDM que pour `tas` (calibration 1970-2005, mois calendaire, fenêtre de 30 ans), avec pour chaque variable une référence ERA5, une forme et des bornes. Table `VARS` de `src/correction/qdm.py`.

| CORDEX | ERA5 | Conversion | Forme | Bornes |
|---|---|---|---|---|
| `tas`, `tasmax`, `tasmin` | `t2m`, `mx2t`, `mn2t` | aucune | additive | |
| `pr` | `tp` (m/j) | ×1000/86400 | occurrence, puis multiplicative sur les jours de pluie (voir plus bas) | ≥ 0 |
| `hurs` | `hurs` | aucune | additive | 0 à 100 |
| `clt` | `tcc` (0 à 1) | ×100 | additive | 0 à 100 |
| `sfcWind` | `si10` | aucune | multiplicative | ≥ 0 |
| `rsds` | `ssrd` (J/m², cumul du jour) | /86400 | multiplicative | ≥ 0 |
| `rlds` | `strd` | /86400 | additive | ≥ 0 |
| `ps` | `sp` | aucune | additive | |
| `evspsbl` | `e` (m, négatif pour l'évaporation) | ×(−1000/86400) | additive | |
| `zg500` | `zg500` | aucune | additive | |
| `alb` = `rsus`/`rsds` | (`ssrd` − `ssr`)/`ssrd` | division par max(`rsds`, 1 W/m²) des deux côtés | additive | 0 à 1 |

- Forme multiplicative : corrigé = Q_ERA5(τ) × x / Q_CORDEX(τ), les deux quantiles interpolés séparément, le changement du modèle x / Q_CORDEX(τ) plafonné à 10. Là où Q_CORDEX(τ) = 0 (nuit polaire), x est gardé.
- Valeurs égales (0 % ou 100 % de `clt`, 0 de `rsds`) : rang du milieu de leur groupe.
- Variables dérivées, après le QDM (`src/correction/derive.py`) :
  - `tn_tx` : `tasmax` et `tasmin` sont corrigés séparément ; les jours où Tn > Tx, les deux valeurs sont échangées. `tas` ne sera pas affiché dans l'application ;
  - `huss` : recalculé à partir de `hurs`, `tas` et `ps` corrigés, avec la formule d'ERA5 (Tetens, sur l'eau). Sur ERA5 1970, cette formule appliquée aux moyennes journalières donne +1 % en moyenne et +11,5 % au P99 par rapport au `huss` d'ERA5, calculé heure par heure ;
  - `rsus` = `rsds` corrigé × `alb` corrigé, pour que `rsus` ne dépasse jamais `rsds`.
- `ps` et `zg500` sont corrigés. Tx reste calé sur `mx2t` (le maximum horaire de `t2m`, plus proche des stations, demanderait un nouveau téléchargement).
- Reportés : le masque mer ; la vérification Tn < Tx au moment de servir une météo (filet de sécurité dans le back-end).

### Contrôles ajoutés

`python -m src.correction.check <variable>` donne en plus :
- pour `pr`, la fréquence des jours secs ; pour les variables bornées, la part de jours aux bornes ;
- des indices sur 1988-2005 (calibration 1970-1987), calculés année par année : jours > 25 et > 30 °C, Tx maximal, plus longue série > 30 °C ; nuits tropicales, jours de gel, Tn minimal, plus longue série de gel ; cumul annuel, jours ≥ 1 mm, pluie maximale en 1 et 5 jours, plus longue série sèche, durée moyenne des séries sèches ; persistance jour à jour (corrélation des anomalies au mois) pour toutes les variables.

Pour `huss` et `rsus`, `check` compare les fichiers finaux à ERA5 sur 1988-2005, années incluses dans la calibration : ce n'est pas une validation indépendante.

`python -m src.correction.spells` : séries sèches par saison, 1970-2005, ERA5, brut et corrigé, médianes par région et cartes.

Validation par tirage d'années au hasard (18 ans de calibration, 18 de validation, tirage répété), en plus du découpage chronologique : proposée, non retenue pour le moment.

### Pilote : `tasmax`, `tasmin`, `hurs`, `pr` (27/09/2026)

**`tasmax`, `tasmin`.** Même qualité que `tas`. Validation croisée : biais moyen de −0,6 à −2,8 K brut, de −0,75 à +0,2 K corrigé. Signal moyen conservé à 0,02 K près sur le domaine ; au P95, écart jusqu'à 8 K en hiver dans les mailles de neige et de glace.

| Indice, 1988-2005, moyenne sur le domaine | ERA5 | brut | corrigé | RMS entre mailles, brut → corrigé |
|---|---|---|---|---|
| jours Tx > 30 °C par an | 20,0 | 17,9 | 18,7 | 8,9 → 3,6 |
| plus longue série Tx > 30 °C (j) | 12,7 | 10,5 | 11,8 | 8,5 → 3,5 |
| nuits tropicales par an | 26,5 | 14,5 | 24,5 | 24,7 → 4,8 |
| jours de gel par an | 73,0 | 90,0 | 73,2 | 26,0 → 6,1 |
| persistance jour à jour (Tx) | 0,75 | 0,76 | 0,75 | inchangée |

**Échange Tn/Tx.** Le brut n'a aucun jour Tn > Tx ; la correction séparée en crée. 21 millions de valeurs échangées sur 1970-2100, de 0,4 % des jours-mailles au début à 1,1 % en 2100. En 1990 : écart médian 0,4 K, P99 4,4 K. Surtout dans les mailles mixtes terre-mer (îles de l'Égée, cap Corse, Minorque : jusqu'à 24 % des jours). Même phénomène observé dans la V1 avec la correction d'Open-Meteo.

**`hurs`.** RMS entre mailles de 6 à 7 % brut, 2 à 2,8 % corrigé. Biais résiduel de +0,5 à +1 % d'avril à septembre : le biais du modèle a changé entre 1970-1987 et 1988-2005 (ERA5 s'assèche sur terre, pas le modèle). Signal et persistance conservés.

**`pr` : historique.**

1. Méthode de Cannon (2015) : valeurs sous 1 mm/j remplacées par des tirages au hasard entre 0 et 1 mm, rapport Q_ERA5/Q_CORDEX plafonné à 10, valeurs corrigées sous 1 mm mises à 0. Cumul annuel et jours de pluie corrigés, mais séries sèches raccourcies de 5 à 10 % partout : les jours secs à rendre pluvieux sont choisis au hasard et coupent les séries. Le raccourcissement apparent sur le domaine (durée moyenne 7 jours contre 12 dans ERA5) venait surtout du sud (Sahara, Moyen-Orient), où le modèle fait pleuvoir ; en Europe, le brut est proche d'ERA5 (médiane terre, été : 3,2 jours pour les deux).
2. Premier correctif : tirages sur les zéros seulement (la bruine garde sa valeur et son ordre), et forme multiplicative écrite comme ci-dessus. Séries sèches réparées (durée moyenne sur le domaine 11,8 jours, ERA5 12,4 ; plus longue série 45,2 contre 47,0 ; sud de 35 N en été 75 jours contre 77). Mais signal amplifié en montagne, où ERA5 est bien plus pluvieux que le modèle : Alpes maritimes (44,5 N 7,25 E), juin, brut 2,2 → 3,3 mm/j (+51 %), corrigé 5,6 → 14,4 mm/j (+154 %). En juin, 1 793 mailles sur 37 633 ont un signal décalé de plus de 10 points, 65 de plus de 20. Cause : à un rang où le modèle passé n'a que de la bruine (0,1 mm) et ERA5 déjà 5 mm, un futur à 1,5 mm donne un changement de 15, plafonné à 10, soit 50 mm. Les tirages de Cannon masquaient ce défaut en remontant les petits quantiles du modèle.
3. Un plancher sur le dénominateur a été envisagé, puis écarté : troisième rustine non publiée.

**`pr` : méthode retenue (version 3).** Occurrence puis intensité (adaptation de fréquence de Themeßl et al. 2012, reprise dans xclim/xsdba, puis QDM sur les jours de pluie). Fonctions `calibrate` et `correct` de `qdm.py`, reprises par `check.py` et `violin.py`. Plus aucun tirage au hasard.

1. Occurrence. Pour chaque maille et chaque mois, sur 1970-2005 : seuil du modèle = valeur qui laisse sous elle la même proportion de jours que la proportion de jours secs (< 1 mm) d'ERA5. Le même seuil sert de 1970 à 2100 : l'évolution du nombre de jours de pluie du modèle est conservée.
2. Sous le seuil, valeur 0. Les jours qui basculent sont choisis selon leur quantité.
3. Intensité : QDM multiplicatif entre les jours du modèle au-dessus du seuil (fenêtre de 30 ans pour le rang) et ceux d'ERA5 ≥ 1 mm, quantiles calculés sans les jours secs.
4. Moins de 30 jours pluvieux sur 1970-2005 dans ERA5 ou dans le modèle, pour une maille et un mois : occurrence corrigée, quantités laissées brutes (juillet : 9 398 mailles, Sahara et Moyen-Orient).
5. Modèle trop sec (plus de jours à 0 exact qu'ERA5 n'a de jours secs, environ 230 mailles désertiques en janvier et juillet) : seuil = plus petite valeur positive. Tous les jours de pluie du modèle sont gardés ; l'occurrence reste trop basse.

La table `pr_quantiles_1970-2005.nc` contient en plus le seuil (`threshold`) et le nombre de jours pluvieux d'ERA5 et du modèle (`n_ref`, `n_hist`).

Résultats (`check pr`, validation croisée, moyenne sur le domaine, RMS entre mailles entre parenthèses) :

| Indice, 1988-2005 | ERA5 | brut | version 2 | version 3 |
|---|---|---|---|---|
| cumul annuel (mm) | 779 | 827 (201) | 790 (92) | 774 (73) |
| jours ≥ 1 mm par an | 140,4 | 141,9 (21,5) | 146,8 (11,6) | 142,9 (7,5) |
| plus longue série sèche (j) | 47,0 | 38,0 (31,8) | 45,2 (10,1) | 47,3 (9,9) |
| durée moyenne des séries sèches (j) | 12,4 | 7,3 (20,6) | 11,8 (7,6) | 14,4 (12,9) |

- Signal, juin : mailles dont le signal est décalé de plus de 10 points, 1 793 en version 2, 824 en version 3 ; de plus de 20 points, 65 et 7. Alpes maritimes : brut +51 %, version 2 +154 %, version 3 +79 %. Nord-est de la Turquie (40,5 N 41,25 E) : +43 %, +112 %, +75 %. Une amplification subsiste en montagne, divisée par deux ou trois.
- Jours qui basculent (1970-2005) : environ 6 % des jours en médiane, 16 à 17 % au P95 des mailles. Ce sont des jours gris : en juillet, anomalie d'humidité brute de +2,9 à +3,5 % et d'amplitude Tx − Tn de −0,4 à −0,6 K, entre les jours secs (−2,3 %, +0,3 K) et les jours pluvieux (+4,8 %, −0,7 K).
- Jours de pluie corrigés sous 1 mm : 0,1 à 0,2 % des jours de pluie. Pas de plancher.

**Défaut accepté : les déserts.** L'écart sur la durée moyenne des séries sèches (14,4 j contre 12,4) vient entièrement des mailles à moins de 20 jours de pluie par an (sud de 35 N) ; ailleurs, écart médian −0,2 j (Europe terre : 4,0 j contre 4,2). En validation croisée, le seuil y repose sur 4 ou 5 jours du modèle en 18 ans : 26 N 0,25 E, 3 jours de pluie par an dans ERA5, 0,2 corrigé. Sur le calage complet, juillet : 0,40 % de jours de pluie contre 0,47 % ; janvier : 0,78 % contre 1,71 %. Dans les mailles à quantités brutes, un jour de pluie de juillet apporte 5,7 mm contre 2,9 mm dans ERA5, pour une moyenne mensuelle juste (0,03 mm/j). Accepté, comme le défaut de `tas` dans les zones froides, qui est plus gênant car dans la zone d'intérêt : ERA5 est peu fiable dans ces déserts, en bordure du domaine. Ces mailles seront signalées par l'indicateur de fiabilité (critère immédiat : `n_ref` ou `n_hist` < 30).

**Point ouvert.** Avec le domaine CORDEX Afrique, le Sahara sera au centre du domaine : à reprendre, par exemple avec un seuil calé sur plusieurs mois voisins.

Sorties : `check_pr.log`, `pr_spells.log`, `pr_analyse.log` (signal en montagne, jours qui basculent, mailles sèches), `pr_series_seches.log` ; celles de la version 2 portent le suffixe `_v2`.

**État au 27/09/2026.** Les fichiers `pr` de `eur11_025_qdm` sont ceux de la version 3. `sfcWind` et `rsds` utiliseront la forme multiplicative ci-dessus. Les 9 autres variables (`huss` remappé pour comparaison, `clt`, `sfcWind`, `rsds`, `rlds`, `rsus`, `ps`, `evspsbl`, `zg500`, puis `alb`, `huss` et `rsus` dérivés) restent à corriger : environ 7 h de calcul, à lancer sous `caffeinate`, chargeur branché (le Mac se met en veille profonde sur batterie, ce qui suspend le calcul et peut provoquer un message de disque mal éjecté ; les fichiers de la nuit du 26 au 27 ont été relus sans erreur).

Mode test : avec `WSA_QDM_TEST=1`, `qdm`, `check`, `spells` et `violin` écrivent et lisent dans `eur11_025_qdm_test/` et `data/correction/test/`.

## Fichiers

| Fichier | Contenu |
|---|---|
| `data/correction/poids_eur11_era5.npz` | poids du remappage CORDEX vers ERA5 |
| `data/correction/<variable>_quantiles_1970-2005.nc` | quantiles ERA5 et CORDEX par mois et par maille |
| `data/correction/check_<variable>.log`, `pr_spells.log`, `pr_analyse.log`, `pr_series_seches.log`, `*_validation.png`, `pr_spells.png` | sorties des contrôles (`*_v2` : version 2 de `pr`) |
| `data/correction/derive_tn_tx.log` | nombre de valeurs Tn/Tx échangées par année |
| `LaCie/.../cordex/eur11_025/` | CORDEX remappé à 0,25°, brut |
| `LaCie/.../cordex/eur11_025_qdm/` | CORDEX remappé à 0,25°, corrigé |
