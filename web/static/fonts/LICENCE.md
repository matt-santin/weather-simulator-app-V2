# Les trois fichiers

Embarquées dans le projet, servies depuis `/static/fonts/`. **Aucune requête
vers un tiers à l'affichage** : la page reste servable sous une politique de
sécurité stricte, et rien ne se décale au chargement faute d'une ressource
distante qui tarde.

Ce sont des fontes **variables** : un seul fichier porte toute la plage de
graisses, donc une requête au lieu de quatre, et aucune graisse synthétique.
Vérifié plutôt que supposé — à 100 px, *Hamburgefonstiv* mesure 682 px en 400 et
737 px en 700.

| Fichier | Fonte | Emploi | Poids |
|---|---|---|---|
| `inter.woff2` | Inter | texte courant, formulaire, mesures | 47 Ko |
| `eb-garamond.woff2` | EB Garamond | titres, valeurs, sous-titres | 43 Ko |
| `eb-garamond-italic.woff2` | EB Garamond italique | **en réserve** — rien ne l'emploie | 47 Ko |

Sous-ensemble latin uniquement — le site est en français, et le jeu complet
pèserait plusieurs fois cela.

**L'italique est déclaré mais plus employé, et le fichier reste.** Les
sous-titres l'ont abandonné : celui de Garamond a la plus petite hauteur d'x des
fontes examinées — 41 px contre 44 à 53 à corps égal — et l'avertissement en
devenait pénible à lire sur le couchant.

Le fichier est conservé parce qu'il **ne coûte rien tant qu'il ne sert pas** :
un `@font-face` que rien n'appelle n'est jamais téléchargé. Le retirer
signifierait qu'un `<em>` écrit un jour ferait pencher le romain par le
navigateur, ce qui déforme les lettres au lieu de les dessiner. Quarante-sept
kilo-octets dans le dépôt, zéro sur le réseau, et l'alphabet est là le jour où
une citation en aura besoin.

EB Garamond remplace Source Serif 4, retirée du dépôt le jour du changement :
elle n'était plus servie, et une fonte de 119 Ko que personne ne charge est du
poids que quelqu'un finit par croire nécessaire.

## Licence

Les deux sont publiées sous **SIL Open Font License 1.1**, qui autorise
l'usage, la modification et la redistribution, y compris embarquée dans un
site. Le texte de la licence :

- Inter — <https://github.com/rsms/inter/blob/master/LICENSE.txt>
- EB Garamond — <https://github.com/octaviopardo/EBGaramond12/blob/master/OFL.txt>

## Les remplacer

Déposer le `.woff2` ici et changer la déclaration `@font-face` correspondante
dans `web/static/css/style.css`. Les règles de la feuille lisent les jetons
`--font` et `--font-display`, jamais un nom de fonte en dur.
