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

ERA5 n'intervient que dans la calibration. La fenêtre glissante sert seulement à situer chaque jour dans le climat du modèle à son époque. Un jour de rang 20 % reçoit la même correction b(20 %) en 1987 et en 2080, même s'il est plus chaud en 2080 : le réchauffement simulé par le modèle, quantile par quantile, est conservé.

Entre deux quantiles, τ et b sont interpolés linéairement. Sous 0,5 % et au-dessus de 99,5 %, on applique la correction du quantile extrême.

`python -m src.correction.qdm tas`

## 3. Exemple : Paris, janvier 1970-2005

![Distributions ERA5, CORDEX brut et corrigé, Paris, janvier](../figures/correction/tas_paris_01_violin.png)

- Les moyennes brutes sont presque égales : 3,69 °C pour ERA5, 3,52 °C pour CORDEX. Une correction de la moyenne ajouterait +0,17 K à tous les jours.
- Les formes diffèrent : CORDEX n'a presque pas de queue froide (minimum −8,7 °C contre −12,7 °C). Il est trop chaud de 1,2 K au P5, et trop froid de 0,2 à 0,6 K au-dessus du P25.
- b(τ) refroidit donc les jours froids (jusqu'à −3 K pour le 1 % le plus froid) et réchauffe les autres de 0,2 à 0,6 K.
- Après correction, l'écart à ERA5 est de −0,1 à +0,1 K entre P25 et P95, et de +0,2 K au P5. Le minimum corrigé est −11,7 °C.

L'écart résiduel dans la queue froide a deux causes. D'une part, chaque année est classée dans sa propre fenêtre de 30 ans, pas dans 1970-2005. D'autre part, les quantiles extrêmes reposent sur une dizaine de jours.

`python -m src.correction.violin tas 48.86 2.35 1 Paris`

## 4. Validation

`python -m src.correction.check tas`

**Validation croisée.** On calibre sur 1970-1987, puis on corrige et on compare à ERA5 sur 1988-2005. Le biais moyen passe de −1,1 à −2,5 K à une valeur entre −0,6 et +0,2 K, selon le mois. L'erreur quadratique entre mailles passe de 1,8 à 3,3 K à 0,5 à 1,7 K.

**Conservation du signal.** On compare l'écart entre 2071-2100 et 1976-2005, avant et après correction. De mai à octobre, il est conservé à quelques centièmes de K près en moyenne sur le domaine.

**Limite identifiée.** En hiver, dans environ 2 000 mailles, le modèle a une surface qu'ERA5 n'a pas : banquise au nord de l'Islande et en mer de Barents, neige et glaciers des Alpes et du Caucase, Caspienne. Dans ces mailles, les jours froids de CORDEX sont trop froids de 15 à 25 K, alors que les jours chauds sont presque justes. Quand le modèle perd cette banquise ou cette neige dans le futur, le QDM déforme le signal : au nord de l'Islande, le P95 de janvier passe de +2,5 K (brut) à +14,5 K (corrigé). Le traitement de ces mailles reste à décider.

## Fichiers

| Fichier | Contenu |
|---|---|
| `data/correction/poids_eur11_era5.npz` | poids du remappage CORDEX vers ERA5 |
| `data/correction/tas_quantiles_1970-2005.nc` | quantiles ERA5 et CORDEX par mois et par maille |
| `LaCie/.../cordex/eur11_025/` | CORDEX remappé à 0,25°, brut |
| `LaCie/.../cordex/eur11_025_qdm/` | CORDEX remappé à 0,25°, corrigé |
