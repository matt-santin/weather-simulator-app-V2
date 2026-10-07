# CLAUDE.md

Ce document est consacré à guider Claude Code pour la V2 du projet d'application de simulation météo, dont une première version V1 a été faite et publiée sur https://github.com/matt-santin/weather-simulator-app.  

# Objectif du projet 

L'idée de ce projet est de créer une application permettant de voir à quoi pourrait ressembler la météo dans le futur, en fournissant à l'utilisateur des résultats similaires à ceux d'une application météo classique. L'originalité est de proposer une séquence météo en n'importe quel lieu, mais surtout à n'importe quel moment. La météo passée est celle issue de modèles de réanalyse météo historique, celle du futur est issue d'une météo simulée en tenant compte du réchauffement climatique. Le but est de sensibiliser le public en lui montrant à quoi pourrait ressembler un été en 2040 ou en 2070, n'importe où dans le monde. 

## Résumé de la V1

La première version du projet a été déployée à l'adresse suivante : https://weathersimulatorb44c76e3-weather-simulator.functions.fnc.fr-par.scw.cloud/resultats?lieu=Grenoble&lat=45.17869&lon=5.71479&debut=2044-06-21&fin=2044-09-20

Elle a rempli tous ses objectifs, mais il faudrait désormais aller plus loin : comparer la séquence météo affichée avec les normales de la même période, afficher des cartes de séquences météo, intégrer les risques associés à la météo, etc. La version actuelle est limitée par le quota API de la source de données, Open-Meteo. Ces améliorations sont impossibles à réaliser dans le cadre de la V1 : un utilisateur lambda serait vite bloqué par le quota dès l'affichage d'une carte.

## Résumé de la V2

Cette version V2 a pour but de modifier profondément la source de données et le fonctionnement en back-end de l'application. Les données seront désormais intégralement téléchargées et stockées en dur sur un HDD, puis seront déployées avec l'application. La question du coût du stockage et de l'exploitation des données sera un sujet majeur pour ce projet, le dataset étant de l'ordre du To. L'utilisateur pourra entrer sur le site tel qu'il se présente aujourd'hui, mais il aura accès, pour le lieu où il se situe, depuis la page de résultats, à une comparaison aux normales, à un diagramme climatique passé, actuel et futur, mais aussi un résumé global des saisons de chaque année jusqu'en 2100. Le design et l'ergonomie de cette page sont à préciser. Il faudra aussi proposer une série de cartes sur une zone géographique donnée (par exemple une animation des températures maximales sur l'Europe de l'Ouest sur un été complet). L'intégration des risques sera à décider pour cette V2 ou une potentielle V3 : par exemple, arriver à qualifier chaque saison (par exemple "humide", "sèche", "caniculaire", etc.), sortir des séquences météo notables (séries de jours sans pluie ou à températures élevées), voire intégrer les potentiels de production agricole sur une année donnée.

# Choix actés pour la V2 - différences par rapport à la V1

## Choix du modèle  

Pour cette V2, le critère principal était de disposer des données en dur, afin de s'affranchir de la dépendance d'Open-Meteo. J'ai essayé de retrouver les données fournies par le modèle `MRI_AGCM3_2_S`, mais celles-ci ne semblent plus être accessibles. Un mal pour un bien, autant changer de modèle et une recherche a permis de fouiller sur le Copernicus Data Store (CDS), sur lequel il y a plein de modèles disponibles, avec plus de possibilités. 

J'en profite pour rehausser les critères : une météo journalière jusqu'en 2100 (2050 était un peu juste : "seulement" 24 années dans le futur), un maximum de paramètres pour calculer le plus d'indicateurs possibles avec une meilleure fiabilité que précédemment (la nébulosité posait problème), avec une bonne résolution spatiale, à l'échelle mondiale. 

### Simulation de la météo future : CORDEX

On utilise CORDEX, un programme d'expériences coordonnées du WCRP. Il fixe un protocole commun (domaines, résolutions, périodes, scénarios, format des sorties) pour produire des simulations. Il est basé sur le couple modèle global ou pilote/modèle régional : le modèle global tournant sur la totalité de la planète avec des grosses mailles (100kmx100km) et le modèle régional recentré uniquement sur une région du globe, avec une maille fine (0,44° ou 0,22°, soit 50 ou 25 km, voire 0,11°, soit 12 km, en Europe) en prenant en compte les grandeurs du modèle global en conditions aux limites. Les données sont extraites ici : https://cds.climate.copernicus.eu/datasets/projections-cordex-domains-single-levels?tab=overview

Voici les choix retenus :
pilote    `ichec_ec_earth`   (EC-Earth2, CMIP5, membre r12i1p1)
régional  `smhi_rca4`
domaine   `EUR-11`, 0,11°, soit 12 km
scénario  `rcp_4_5`, `historical` avant 2006

Le modèle pilote `ichec_ec_earth` est celui qui propose le plus de régions du monde ; `smhi_rca4` est celui qui accepte le plus de modèles pilotes. On commence par l'Europe, puis on étendra aux autres domaines CORDEX : à terme, on vise le monde entier. 
Il y a plusieurs choix de scénarios d'émission ; CORDEX en accepte 3 : rcp 2.6, rcp 4.5 et rcp 8.5. On retient le deuxième, qui semble le plus cohérent avec la trajectoire climatique actuelle. 

Le scénario `rcp_4_5`, `historical` correspond au forçage radiatif (GES, aérosols, usage des sols) : toutes les données `historical` (avant 2006) correspondent à une météo plausible sous le forçage radiatif observé jusqu'en 2005 (même concentration de CO2 que la réalité), mais la météo affichée ne correspond pas à des événements réels. À partir de 2006, c'est le scénario `rcp_4_5` qui impose le forçage (trajectoire climatique).

Les noms des fichiers téléchargés se lisent tous de la manière suivante : 
```
clt_EUR-11_ICHEC-EC-EARTH_historical_r12i1p1_SMHI-RCA4_v1_day_19850101-19851231.nc
 │      │          │           │        │         │      │   │         │
 │      │          │           │        │         │      │   │         └── période couverte
 │      │          │           │        │         │      │   └── pas de temps
 │      │          │           │        │         │      └── version du modèle régional
 │      │          │           │        │         └── modèle régional (RCM)
 │      │          │           │        └── membre d'ensemble du pilote
 │      │          │           └── expérience
 │      │          └── modèle global pilote (GCM)
 │      └── domaine et résolution
 └── variable
```

#### Changement de modèle : CORDEX-CMIP6 (octobre 2026)

Le couple EC-EARTH / RCA4 s'est révélé trop froid : 1,8 K de biais froid sur les Tx d'été en France (2006-2025, brut) et un réchauffement en retard de 15 à 20 ans sur le climat observé (`docs/resultats_rcp45.md`). Le 6/10/2026, il a été décidé de le remplacer par une simulation de la nouvelle génération EURO-CORDEX, pilotée par CMIP6 :
pilote    `MPI-ESM1-2-HR`   (CMIP6, membre r1i1p1f1)
régional  `ICON-CLM-202407-1-1` (CLMcom-DWD)
domaine   `EUR-12`, 0,11°, soit 12 km (même type de grille que EUR-11, pôle tourné)
scénario  `ssp370`, `historical` avant 2015

Justification (modèles plus récents, aérosols variables, biais brut quasi nul sur la France, modèles globaux retenus par EURO-CORDEX et bien évalués, pas de palier des Tx d'été dans les années 2030-2040 contrairement à CNRM-ESM2-1) : `docs/choix_modele_cmip6.md`. CORDEX-CMIP6 n'est pas sur le CDS : les données viennent d'ESGF. Noms de fichiers, version, licence et attribution : `data/cordex/eur12_mpi-esm1-2-hr_icon-clm/PROVENANCE.md`. Ce modèle reste lui aussi en retard sur le réchauffement récent, comme toutes les simulations CMIP6 testées : un ajustement sur la TRACC est à décider.

Le site sert RCA4 corrigé tant que MPI-ESM1-2-HR / ICON-CLM n'est pas corrigé.

Les variables téléchargées sont les suivantes : 
| Nom | Unité | Grandeur |
|---|---|---|
| `tas` | K | température de l'air à 2 m, moyenne |
| `tasmax` | K | température maximale à 2 m |
| `tasmin` | K | température minimale à 2 m |
| `hurs` | % | humidité relative à 2 m |
| `huss` | sans | humidité spécifique à 2 m |
| `pr` | kg m⁻² s⁻¹ | flux de précipitation |
| `clt` | % | nébulosité totale |
| `sfcWind` | m s⁻¹ | vitesse du vent à 10 m |
| `rsds` | W m⁻² | rayonnement solaire descendant à la surface |
| `rlds` | W m⁻² | rayonnement infrarouge descendant à la surface |
| `rsus` | W m⁻² | rayonnement solaire réfléchi par la surface |
| `ps` | Pa | pression à la surface |
| `evspsbl` | kg m⁻² s⁻¹ | évaporation |
| `zg500` | m | hauteur géopotentielle à 500 hPa |

### Météo passée : ERA5

Pour les données météo du passé, on utilise la réanalyse ERA5, éprouvée dans la V1, à 0,25° (environ 28 km). Les statistiques journalières sont téléchargées depuis le CDS et stockées en dur. 

## Analyse des données 

On souhaite s'assurer que chaque variable servie par CORDEX n'est pas biaisée par rapport à la réalité, dans le temps (mois par mois) et dans l'espace (point par point). On compare donc à des observations réelles, ou plus exactement avec la réanalyse ERA5 (qui n'est pas une observation directe, mais un modèle calibré avec les observations météo).

Pour chaque variable, à chaque lieu et à chaque mois de l'année, on va moyenner sur toutes les années disponibles et sur tous les jours du mois. On obtient ainsi une grille contenant, pour chaque point, l'écart/rapport moyenné sur 36 ans (1970-2005) x 30 jours entre ERA5 et CORDEX pour tous les mois de l'année. On appliquera ainsi cette correction sur toutes les données servies par CORDEX sur les données du futur. On fait ainsi l'hypothèse que les écarts ou les rapports restent constants malgré l'amplification du réchauffement climatique. Pour chaque maille ERA5, on regarde quelles mailles CORDEX la recouvrent, avec quel poids et on fait une moyenne pondérée. 

Les détails sont enregistrés dans `docs/correction.md`. Les températures (`tas`, `tasmax`, `tasmin`) sont aussi corrigées à 0,1° contre ERA5-Land (section 9) ; ce sont elles que sert le site.

## Interface de l'application

/!\ À faire

Le site de la V1 est branché sur les données V2 (ERA5-Land et ERA5 1970-2025, CORDEX corrigé 2027-2100, 2026 indisponible) : voir `docs/application.md`.

### Comparaison aux normales

### Diagramme climatique

### Matrice des années

### Carte animée

# Téléchargement des données

CORDEX est téléchargé depuis le CDS, une requête par variable et par année ; CORDEX-CMIP6 depuis ESGF, fichier par fichier tels qu'ESGF les découpe ; ERA5 et ERA5-Land depuis Earth Data Hub (DestinE), en horaire, réduits en journalier (jours UTC) sur l'emprise EUR-11 ; E-OBS (validation) depuis KNMI.
Les données arrivent sur le Mac, puis sont transférées et vérifiées sur le disque externe LaCie (4 To, exFAT), qui n'a pas besoin de rester branché.

| Fichier | Rôle |
|---|---|
| `src/config.py` | chemins communs : données locales (`./data`), disque externe, inventaire de l'archive |
| `src/download/cordex.py` | télécharge CORDEX ; `python -m src.download.cordex 1970-2100` |
| `src/download/era5.py` | télécharge ERA5 horaire et calcule les valeurs journalières, dont `si10`, `hurs`, `huss` et `zg500` ; `python -m src.download.era5 1970-2025` |
| `src/download/era5land.py` | télécharge ERA5-Land (0,1°, terres) : `t2m`, Tx et Tn horaires, `d2m`, `hurs` ; `python -m src.download.era5land 1970-2025` |
| `src/download/cordex6.py` | télécharge CORDEX-CMIP6 (MPI-ESM1-2-HR / ICON-CLM) depuis ESGF, contrôle SHA256, reprise des fichiers interrompus, arrêt sous 20 Go libres ; `python -m src.download.cordex6 tas tasmax --years 1970-2100` |
| `src/download/eobs.py` | télécharge E-OBS (validation de la correction) |
| `src/store/build.py` | construit le stockage de service du site (`data/serve/point.zarr`) |
| `src/archive.py` | copie les fichiers terminés sur le disque externe, les vérifie (MD5), les inscrit dans l'inventaire ; `--free` libère le Mac ; un dossier en argument (`cordex/eur12_mpi-esm1-2-hr_icon-clm`) limite l'archivage à ce dossier |
| `data/archive.txt` | inventaire des fichiers archivés (nom, taille, MD5) : les téléchargements sautent ce qui est déjà sur le disque |
| `data/cordex/eur11/PROVENANCE.md` | origine des fichiers CORDEX (version ESGF, outils du CDS) |
| `data/cordex/eur12_mpi-esm1-2-hr_icon-clm/PROVENANCE.md` | origine des fichiers CORDEX-CMIP6 (ESGF, version, licence, attribution) |
| `data/*/collecte.log` | journaux des téléchargements |
| `requirements.txt` | dépendances Python |

Les clés d'accès sont dans `~/.cdsapirc` (CDS) et `~/.edhrc` (Earth Data Hub). Earth Data Hub est limité à 500 000 requêtes par mois ; ERA5 consomme environ 4 000 requêtes par an, ERA5-Land environ 1 000 (températures et point de rosée).

## CORDEX

Les données sont téléchargées depuis https://cds.climate.copernicus.eu/datasets/projections-cordex-domains-single-levels?tab=overview, avec le choix de modèle, de scénario, de région, etc., explicités ci-dessus. 

CORDEX-CMIP6 (MPI-ESM1-2-HR / ICON-CLM) vient du nœud ESGF du DKRZ (HTTP, sans compte), trouvé par le catalogue STAC d'ESGF (https://api.stac.esgf.ceda.ac.uk, collection `CORDEX-CMIP6`). Le Mac ne peut pas tout contenir : télécharger avec le LaCie branché et archiver au fil de l'eau (`python -m src.archive --free cordex/eur12_mpi-esm1-2-hr_icon-clm`). Les instantanés locaux de Time Machine retiennent les fichiers supprimés : `tmutil thinlocalsnapshots / 300000000000 4` rend la place.

## ERA5 

Téléchargé depuis Earth Data Hub (Zarr horaire), réduit en journalier (jours UTC) par `src/download/era5.py`. Mêmes données que le CDS, arrondies par Earth Data Hub (pas de 0,25 K sur `t2m` vers 280 K). Le CDS a été abandonné : plusieurs heures d'attente par requête.

## ERA5-Land

Téléchargé depuis Earth Data Hub (`reanalysis-era5-land-no-antartica-v0`), 0,1°, terres seulement, par blocs natifs de 120 jours pour ne compter chaque bloc qu'une fois. Sert de référence aux températures à 0,1°.

## État

Au 02/10/2026, tout est sur le LaCie, vérifié (MD5) et listé dans `data/archive.txt` :
- CORDEX : 1970-2100, 14 variables, 1834 fichiers, 168,9 Go ;
- ERA5 : 1970-2025, 17 champs journaliers, 952 fichiers, 51,0 Go ; l'horaire n'est pas conservé ;
- CORDEX-CMIP6 MPI-ESM1-2-HR / ICON-CLM (au 07/10/2026) : 1966-2100, 14 variables plus `sftlf` et `orog`, 394 fichiers, environ 322 Go, sur le LaCie seulement ; pas encore corrigé ;
- ERA5-Land : 1970-2025, 5 champs journaliers, 280 fichiers, 41,2 Go ;
- E-OBS v33.0e : 0,25° (sur le Mac et le LaCie) et 0,1° (sur le LaCie seulement) ;
- stockage de service : 71 Go, aussi sur le Mac, lu par le site local.

Restent seulement sur le Mac : `data/era5/_test` (janvier 1970, tests) et `data/cordex/mensuel` (9,7 Go : `tas` et `tasmax` mensuels des simulations CORDEX-CMIP6 comparées pour le choix du modèle, `figures/climat/cmip6_tri.py`).

# Déploiement

Le déploiement de l'application pose de nouvelles problématiques vis-à-vis de la V1 : cette dernière pèse en tout et pour tout quelques Mo, chaque requête quelques ko. Cette V2 exploite sa propre base de données, dont l'ordre de grandeur est le To. Le site utilisera toujours quelques ko pour les fonctionnalités de base (affichage d'une séquence météo), mais les améliorations de la V2 seront plus lourdes, comme les cartes (potentiellement quelques Mo). Il faut donc soigneusement choisir l'infrastructure afin d'assurer un fonctionnement efficace sans dérapage financier lors du déploiement. 

Cette étape sera discutée plus en détail lorsque la V2 sera plus avancée en local. 

# À faire

/!\ Ne pas en tenir compte pour le moment
Téléchargement
Analyse scientifique 
Amélioration du front
Test du pipeline
Déploiement
Communication

# Règles 

Je suis de formation scientifique (doctorat), mais avec peu de connaissances en backend et frontend. Le rôle de Claude Code sera principalement de développer la partie backend et frontend, et dans une moindre mesure, de m'assister sur la partie scientifique (résumé d'articles, de pages web, répondre aux questions scientifiques, etc.).

 - Je rédige le CLAUDE.md, sauf si je dis à Claude Code de le faire ;
 - On ne sort pas du dossier ./Projets_data, sauf pour installer si besoin des environnements virtuels ;
 - Je veux que Claude Code m'explique ce qu'il va faire avant de le faire ; les initiatives sont toutefois bienvenues ;
 - Pas de tirets quadratins, nulle part ;
 - Sois concis, clair et froid lors des échanges ou de la rédaction de documents ;
 - Je gère la partie scientifique (choix des modèles, etc.) ;
 - Claude Code peut être relativement autonome sur la partie dev frontend ;
 - Sur la partie back-end, Claude Code est libre d'écrire le code à sa guise, en sachant que je décide de l'infrastructure au vu de l'enjeu (la facture peut vite déraper)
 - Pour l'aspect scientifique, tout chiffre ou résultat "connu" que tu évoques doit être contrôlé depuis une source sûre (publication scientifique, météofrance, etc)