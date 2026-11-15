# Neige au sol : essai du 14/11/2026

Essai de calcul des jours de neige au sol à partir des données que le site sert. Intégré au site le 14/11/2026, dans le climat du lieu (section 10, `docs/application.md` section 15). Scripts dans `figures/neige/`, données intermédiaires dans `data/neige/` (non versionnées).

## 1. Objet et choix

Le site ne connaît que la neige qui tombe (jour de précipitation sous 1,5 °C de température moyenne, `src/app/domain/thresholds.py`), pas la neige au sol.

Deux voies possibles :

- A. Prendre la neige du modèle. MPI / ICON publie sur ESGF, en journalier, `snc` (fraction enneigée, 4,7 Go), `snd` (hauteur, 5,9 Go), `snw` (équivalent en eau, 5,9 Go) et `prsn` (chutes, 32,5 Go), `historical` et `ssp370`. Non téléchargés. Cette neige est calculée avec les températures et pluies brutes du modèle, sur son relief à 12 km.
- B. La calculer à partir des températures et précipitations servies. Retenue le 14/11/2026 : même calcul pour le passé et le futur, cohérent avec les journées affichées, rien à télécharger.

## 2. Méthode

Degré-jour, pas journalier, en un point :

- chute : la précipitation du jour s'ajoute au stock quand la température moyenne (`tas`) est sous `Ts` ;
- fonte : `DDF × max(tas, 0)` mm par jour ;
- stock remis à zéro le 1er août ;
- neige au sol : stock d'au moins `S0` mm d'équivalent en eau.

Grandeur évaluée : nombre de jours de neige au sol de novembre à avril, par hiver (hiver nommé par son année de fin).

## 3. Référence

Hauteurs de neige journalières des stations ECA&D (`data/stations/ecad/blend/ECA_blend_sd.zip`, 988 Mo, téléchargé le 14/11/2026, `data/stations/PROVENANCE.md`). Neige au sol observée : hauteur de 1 cm ou plus (`SNOW_DEPTH_CM`). 11 390 séries, 7 436 avec au moins la moitié des jours de juillet 1970 à juin 2020.

Échantillon lu : 1 589 stations dans le domaine avec une maille à 0,1° (1 500 tirées au hasard, plus celles de France, Suisse, Autriche et Italie), dont deux tiers en Allemagne. Un hiver compte s'il a au moins 95 % de jours valides. Températures et précipitations : celles que le site sert à la maille de la station (E-OBS pour `tas`, ERA5 pour `pr`).

## 4. Calage et contrôle

60 à 72 combinaisons de `Ts` (0,5 à 2 °C), `DDF` (1 à 5 mm par °C et par jour) et `S0` (1, 2, 5 mm), classées par l'erreur absolue moyenne entre stations (jours par hiver). Calage sur les hivers 1971-2000 (1 464 stations), contrôle sur 2001-2020 (1 265 stations), non vus au calage.

Réglage retenu : `Ts` = 0,5 °C, `DDF` = 4 mm, `S0` = 2 mm. Erreur 8,7 jours au calage, 7,3 au contrôle. Les réglages sont peu contraints : 1,0 °C, 5 mm, 2 mm fait aussi bien ; 1,5 °C (seuil du pictogramme), 3 mm, 5 mm fait 9,4 et 7,9.

Contrôle sur 2001-2020 :

| Altitude | Stations | Observé | Calculé | Erreur absolue | Biais | Corrélation entre hivers (médiane) |
|---|---|---|---|---|---|---|
| moins de 300 m | 823 | 28,6 | 32,0 | 6,3 | +3,4 | 0,94 |
| 300 à 800 m | 406 | 52,2 | 54,1 | 7,4 | +2,0 | 0,94 |
| 800 à 1 500 m | 31 | 102,8 | 87,7 | 28,1 | −15,0 | 0,87 |
| 1 500 m et plus | 5 | 180,5 | 151,8 | 28,7 | −28,7 | nulle |

Tendance : entre 1971-2000 et 2001-2020, les stations perdent 6,9 jours par hiver, le calcul 5,7 (1 159 stations).

Jour par jour, sous 300 m : environ 81 % des jours de neige retrouvés, 25 à 27 % de fausses alertes.

## 5. Données passées contre modèle corrigé

Jours de neige au sol par hiver, réglage retenu :

| Lieu | 1971-2000 passé | 1971-2000 modèle | 1991-2020 passé | 1991-2020 modèle | 2031-2060 | 2071-2100 |
|---|---|---|---|---|---|---|
| Lyon | 10,9 | 16,2 | 7,6 | 14,0 | 8,6 | 1,9 |
| Strasbourg | 15,1 | 19,8 | 11,8 | 20,0 | 13,3 | 4,7 |
| Besançon | 19,6 | 24,0 | 17,9 | 21,8 | 15,4 | 6,4 |
| Grenoble (ville) | 33,3 | 40,6 | 33,3 | 38,2 | 25,9 | 12,4 |
| Berlin | 23,1 | 28,6 | 19,6 | 24,2 | 11,3 | 6,2 |
| Munich | 44,4 | 46,0 | 36,4 | 40,5 | 28,6 | 15,8 |
| Pontarlier | 69,5 | 70,8 | 64,7 | 68,4 | 53,7 | 29,9 |
| Oslo | 105,8 | 107,5 | 87,4 | 101,6 | 54,0 | 31,2 |

Le modèle corrigé donne plus de neige que les données passées là où il neige peu, y compris sur 1971-2000 : l'écart ne vient pas surtout du retard de réchauffement.

Cause mesurée (1971-2000, novembre à avril, par hiver) :

| Lieu | Jours à 1 mm ou plus : ERA5 / E-OBS / modèle | Jours froids (< 0,5 °C) et humides : ERA5 / E-OBS / modèle |
|---|---|---|
| Lyon | 81,4 / 63,4 / 80,9 | 4,8 / 3,7 / 7,4 |
| Strasbourg | 85,2 / 67,0 / 85,7 | 6,5 / 5,5 / 8,6 |
| Grenoble | 85,9 / 63,9 / 85,5 | 13,1 / 8,9 / 16,8 |
| Berlin | 71,6 / 59,6 / 71,7 | 8,9 / 8,0 / 11,5 |
| Oslo | 65,1 / 57,8 / 67,1 | 35,7 / 32,1 / 35,4 |

La correction donne au modèle le nombre de jours humides d'ERA5 et, à 0,3 K près, sa température d'hiver et son nombre de jours froids. Mais ses jours humides tombent plus souvent par temps froid : le lien entre température et précipitation reste celui du modèle, que la correction par quantiles, faite variable par variable, ne touche pas.

Le retard de réchauffement s'y ajoute sur 1991-2020 : à Lyon, les données perdent 30 % de jours de neige entre 1971-2000 et 1991-2020, le modèle 14 %.

## 6. Pluie d'ERA5 ou pluie d'E-OBS

Les précipitations du site sont celles d'ERA5 ; le modèle est corrigé contre ERA5 (`docs/correction.md`, section 11). Essai : remplacer la pluie d'ERA5 par celle d'E-OBS (`rr`, 0,25°, sur le LaCie) dans les données passées, températures inchangées. 1 508 stations où E-OBS a au plus 1 % de lacunes.

Les deux pluies aux stations, novembre à avril, par hiver :

| | ERA5 | E-OBS |
|---|---|---|
| Jours à 1 mm ou plus | 81,4 | 68,5 |
| Cumul (mm) | 436 | 375 |
| Jours de bruine (0,1 à 1 mm) | 51,8 | 11,6 |
| Jours froids et humides | 20,6 | 17,6 |

Les deux sources s'accordent sur 67 % des jours humides de l'une ou de l'autre.

Neige calculée, chaque pluie calée sur 1971-2000 et contrôlée sur 2001-2020 (1 216 stations) :

| | Pluie ERA5 | Pluie E-OBS |
|---|---|---|
| Réglage (`Ts`, `DDF`, `S0`) | 0,5 °C, 4 mm, 2 mm | 0,5 °C, 3 mm, 1 mm |
| Erreur au contrôle | 6,4 | 6,6 |
| Biais au contrôle | +1,4 | +2,8 |
| Corrélation entre hivers | 0,94 | 0,94 |
| Changement 2001-2020 moins 1971-2000 (observé −8,1) | −7,1 | −6,5 |

Aucun gain pour la neige : le réglage absorbe la différence de pluie, la température domine. L'essai est en partie circulaire (les stations de neige alimentent sans doute E-OBS).

Littérature (résumés lus le 14/11/2026) : E-OBS lisse les précipitations journalières, d'autant plus qu'elles sont fortes (Hofstra et al. 2010) ; ses valeurs sont plutôt basses face à des réseaux plus denses (Hofstra et al. 2009) ; E-OBS (v19.0e) et ERA5 sous-estiment tous deux les quantiles élevés, ERA5 surestime la précipitation moyenne par excès de jours humides, E-OBS est meilleur là où les stations sont denses et les deux se valent ailleurs (Bandhauer et al. 2022) ; l'information d'un jeu sur grille dépend de la densité de ses stations (Prein et Gobiet 2017).

## 7. Sol chaud

Hypothèse : en plaine, le sol encore chaud fait fondre la neige par le dessous, surtout en début de saison. Deux contrôles (réglage retenu, contrôle 2001-2020, stations sous 300 m) :

- biais par mois, observé / calculé : novembre 1,5 / 1,8 ; décembre 5,5 / 5,9 ; janvier 8,9 / 9,1 ; février 7,1 / 7,8 ; mars 4,6 / 5,6 ; avril 1,1 / 1,7. L'excès n'est pas concentré à l'automne ; il est le plus fort en mars ;
- variante avec une fonte par le sol proportionnelle à la moyenne de l'air des 10, 20 ou 30 jours précédents (54 combinaisons) : erreur 8,9 au calage et 7,4 au contrôle, contre 8,7 et 7,3 sans ce terme.

Effet non mesurable à la précision du calcul. L'excès de mars et d'avril fait penser au rayonnement solaire (fonte plus rapide au printemps à température égale) : piste non testée, gain possible d'environ un jour par hiver.

## 8. Montagne

L'échec au-dessus de 800 m vient de l'altitude de la maille, pas du calcul. Essai : ramener `tas` à l'altitude de la station par un gradient vertical fixe, altitude des mailles lue dans `elev_ens_0.1deg_reg_v33.0e.nc` (LaCie), sans recaler la neige.

Contrôle 2001-2020, jours par hiver, calculé (erreur absolue) :

| Altitude | Stations | Observé | Sans correction | 5 K/km | 6,5 K/km |
|---|---|---|---|---|---|
| moins de 300 m | 797 | 28,0 | 31,2 (6,0) | 27,7 (4,7) | 26,8 (5,1) |
| 300 à 800 m | 406 | 52,2 | 54,1 (7,4) | 50,1 (6,7) | 48,7 (8,0) |
| 800 à 1 500 m | 31 | 102,8 | 87,8 (28,1) | 90,5 (15,5) | 91,1 (18,3) |
| 1 500 m et plus | 5 | 180,5 | 151,8 (28,6) | 177,1 (4,5) | 176,8 (5,2) |

Selon l'écart d'altitude entre la maille et la station (stations au-dessus de 800 m, 6,5 K/km) : maille plus basse de 300 m ou plus, erreur 48,9 puis 6,1 (8 stations) ; plus basse de 100 à 300 m, 29,8 puis 14,0 (8) ; à moins de 100 m, 13,5 puis 12,4 (14) ; plus haute de 100 à 300 m, 10,0 puis 35,8 (4) ; plus haute de 300 m ou plus, 78,3 puis 57,3 (2).

Exemples, observé / sans correction / avec 6,5 K/km : Säntis (2 502 m, maille à 906 m) 178 / 95 / 181 ; Brocken (1 142 m, maille à 468 m) 143 / 67 / 156 ; Le Lioran (1 238 m, maille à 1 111 m) 103 / 71 / 92 ; Chamonix (1 042 m, maille à 2 438 m) 104 / 175 / 37.

La correction fonctionne quand le lieu est plus haut que sa maille (sommets, versants). Elle surcorrige les fonds de vallée situés sous une maille de versants : en hiver l'air froid y stagne, le gradient moyen ne vaut pas. Limites : 36 stations au-dessus de 800 m, gradients non calés, pluie non corrigée de l'altitude.

Cette correction vaudrait pour toutes les températures affichées, pas seulement pour la neige (limite de Chamonix dans `docs/application.md`, section 2). Non testée sur les températures elles-mêmes.

## 9. Méthode du rapport

Proposée pour afficher le futur sans hériter de l'excès du modèle :

```
neige future affichée = neige passée observée × (neige du modèle, période future / neige du modèle, période de référence)
```

Lyon, référence 1971-2000 : 10,9 × (8,6 / 16,2) = 5,8 jours en 2031-2060 ; 10,9 × (1,9 / 16,2) = 1,3 jour en 2071-2100. Suite cohérente avec le passé : 10,9 (1971-2000), 7,6 (1991-2020, observé), 5,8, 1,3.

Limites : vaut pour des moyennes sur 20 ou 30 ans, pas pour un hiver donné (il faudrait alors un facteur fixe par lieu, 0,67 à Lyon) ; suppose que l'excès du modèle reste proportionnel ; instable là où le modèle a un ou deux jours en référence ; ne corrige pas le retard de réchauffement, le recul affiché est donc plutôt sous-estimé.

## 10. Décisions

Prises le 14/11/2026 :

| Question | Décision |
|---|---|
| Comment afficher la neige future | méthode du rapport, base 1991-2020 fixe (et non 1971-2000 : la marche entre passé récent et futur proche est plus petite, Lyon 5,5 au lieu de 6,8 jours en 2028-2042 pour 3,9 observés en 2011-2025) ; pas de compte par hiver |
| Fenêtre | les 15 ans du diagramme climatique, pas 30 : baisse presque régulière, ressauts d'un ou deux jours |
| Marche entre 2025 et 2027 | acceptée et dite dans le « ? », comme pour les températures |
| Réglage | 0,5 °C, 4 mm, 2 mm ; le pictogramme de neige qui tombe reste à 1,5 °C |
| Où l'afficher | maille à 800 m au plus, et partout où les températures sont ramenées à l'altitude du lieu (`docs/application.md`, section 16) |
| Neige trop rare | pas de chiffre sous 3 jours par hiver dans le modèle sur 1991-2020 (Bordeaux : facteur 1,48 ou 3,70 selon la base) |

Correction d'altitude des températures : testée et intégrée le 14/11/2026, gradient par mois (`docs/application.md`, section 16 ; `figures/altitude/`).

Ouvertes :

| Question | Proposition |
|---|---|
| Corriger `pr` contre E-OBS | sans effet sur la neige ; à décider pour la pluie affichée (13 jours humides et 16 % de cumul en trop avec ERA5, de novembre à avril) |

## 11. Fichiers

| Fichier | Rôle |
|---|---|
| `figures/neige/stations.py` | lit les séries ECA&D, écrit `data/neige/stations.npz` (90 s) |
| `figures/neige/lire.py` | lit au stockage du site `tas`, `tasmin`, `tasmax`, `pr` aux stations, écrit `data/neige/meteo.npz` (20 s) |
| `figures/neige/calage.py` | calage 1971-2000, contrôle 2001-2020 (section 4) |
| `figures/neige/lieux.py` | lieux, passé et modèle, futur, origine de l'écart (section 5) |
| `figures/neige/lire_pluie_eobs.py` | lit `rr` d'E-OBS aux stations, écrit `data/neige/pluie_eobs.npz` (LaCie) |
| `figures/neige/pluie_eobs.py` | les deux pluies, calage avec chacune (section 6) |
| `figures/neige/lieux_pluie_eobs.py` | lieux avec la pluie d'E-OBS (LaCie) |
| `figures/neige/sol.py` | biais par mois, variante avec fonte par le sol (section 7) |
| `figures/neige/altitude.py` | correction d'altitude (section 8, LaCie) |

Commandes en tête de chaque script, à lancer depuis la racine du dépôt. Les trois fichiers de `data/neige/` (247 Mo) permettent de relancer `calage.py`, `pluie_eobs.py` et `sol.py` sans le LaCie.

## Références

- Bandhauer, M., Isotta, F., Lakatos, M., Lussana, C., Båserud, L., Izsák, B., Szentes, O., Tveito, O. E., Frei, C., 2022 : Evaluation of daily precipitation analyses in E-OBS (v19.0e) and ERA5 by comparison to regional high-resolution datasets in European regions. *International Journal of Climatology*, 42, 727-747. https://doi.org/10.1002/joc.7269
- Hofstra, N., Haylock, M., New, M., Jones, P. D., 2009 : Testing E-OBS European high-resolution gridded data set of daily precipitation and surface temperature. *Journal of Geophysical Research*, 114. https://doi.org/10.1029/2009JD011799
- Hofstra, N., New, M., McSweeney, C., 2010 : The influence of interpolation and station network density on the distributions and trends of climate variables in gridded daily data. *Climate Dynamics*, 35, 841-858. https://doi.org/10.1007/s00382-009-0698-1
- Klein Tank, A. M. G. et al., 2002 : Daily dataset of 20th-century surface air temperature and precipitation series for the European Climate Assessment. *International Journal of Climatology*, 22, 1441-1453. Données : https://www.ecad.eu
- Prein, A. F., Gobiet, A., 2017 : Impacts of uncertainties in European gridded precipitation observations on regional climate analysis. *International Journal of Climatology*, 37, 305-327. https://doi.org/10.1002/joc.4706
