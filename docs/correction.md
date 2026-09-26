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

Piste retenue pour l'instant : garder le QDM, marquer ces mailles par un indicateur de fiabilité (par exemple la corrélation de rang entre brut et corrigé) et les masquer ou les signaler dans l'application. Le traitement de fond est reporté. Essais sur la glace de mer : `docs/notes_correction_glace.md`.

## 5. Correction multivariée (MBCn) : essai

MBCn (Cannon 2018) corrige plusieurs variables ensemble : QDM univarié de chaque variable, puis réordonnancement des jours pour reproduire les liens entre variables d'ERA5. Essai sur 5 mailles (Paris, Grenoble, Alpes 46,5 N 8 E, nord de l'Islande, Botnie), 6 variables : `tas`, amplitude diurne (`tasmax − tasmin`, avec `mx2t − mn2t` pour ERA5), `pr`, `hurs`, `sfcWind`, `rsds`. Réordonnancement à l'intérieur de chaque mois de chaque année, pour garder exactement la distribution univariée de l'année.

- Distributions et réchauffement : identiques à l'univarié, par construction.
- Liens entre variables (écart moyen des corrélations de rang à ERA5 sur 7 paires, validation croisée 1988-2005) : meilleurs dans 8 cas maille-saison sur 10, égaux dans 1, moins bons dans 1 (Paris en été). Gain le plus net aux Alpes en été (0,42 à 0,12).
- Persistance : l'autocorrélation de `tas` d'un jour au suivant baisse, jusqu'à 0,1 (Alpes en hiver : 0,69 à 0,59, ERA5 0,79). Le lien pluie/rayonnement s'affaiblit (Paris en été : −0,69 ERA5, −0,62 univarié, −0,42 MBCn).
- Coût : 0,14 s par transformation N-pdf, soit environ 140 jours de calcul sur un cœur pour le domaine avec le script d'essai ; à réduire par vectorisation et pas de 10 ans, non mesuré.
- Aux Alpes, en été, CORDEX brut est à 0 °C contre 8,3 °C pour ERA5, et le lien température/rayonnement a le mauvais signe : signature probable d'une surface enneigée, à confirmer.

Pas de décision prise. Scripts : `data/correction/tests_mbcn/` (non versionnés).

## Fichiers

| Fichier | Contenu |
|---|---|
| `data/correction/poids_eur11_era5.npz` | poids du remappage CORDEX vers ERA5 |
| `LaCie/.../correction/tas_quantiles_1970-2005.nc` | quantiles ERA5 et CORDEX par mois et par maille |
| `LaCie/.../cordex/eur11_025/` | CORDEX remappé à 0,25°, brut |
| `LaCie/.../cordex/eur11_025_qdm/` | CORDEX remappé à 0,25°, corrigé |
