# WORLD3 — règles, mécaniques et textes

Petit jeu sur le modèle World3 de Meadows, Meadows et Randers : population, industrie, agriculture, pollution, ressources. Le joueur arrive en 2026, au bord du pic du scénario sans décision. Le passé, de 1900 à aujourd’hui, est déjà joué.

Le déroulement est une suite d’étapes. 2026, le globe. Le bouton nomme le prochain conseil (`2030  PROCHAIN CONSEIL`). Les années et les chiffres défilent, la Terre tourne. Un événement peut survenir à n’importe quelle année, environ deux fois tous les dix ans, jamais plus de trois entre deux conseils : on lit la carte, le bouton i explique, `CONTINUER` relance les années. La Terre tourne jusqu’au prochain événement ou au conseil. Au conseil de l’humanité, trois jetons pour les orientations, puis les dilemmes de la décennie, l’un après l’autre. Le choix du dernier ramène au globe. Le bouton y nomme le conseil suivant, par exemple `>> 2040 - PROCHAIN CONSEIL >>`. À l’écran, ces leviers s’appellent des orientations. En 2100, s’il n’y a plus rien à tenir, un message pédagogique. Si le monde tient (`STABLE` ou `RALENTISSEMENT`), on peut continuer, par tranches de cinquante ans, jusqu’en 2200.

Les équations des dix orientations, plus bas, restent celles du modèle. Les textes, les cartes et les fiches se modifient dans l’éditeur : `python -m world3.editor`, qui écrit `contenu.json`.

Les chiffres viennent de World3, pas d’une règle de jeu inventée. Les équations calculées sont celles de 1972. Le récit des scénarios reprend aussi les livres de 1992 et de 2004. Donella H. Meadows, Dennis L. Meadows, Jørgen Randers, William W. Behrens, *The Limits to Growth*, 1972. Dennis L. Meadows et al., *Dynamics of Growth in a Finite World*, 1974. Moteur : PyWorld3 (Charles Vanwynsberghe, licence CeCILL 2.1).

À l’écran, tout est en capitales. La police plie les accents. Les chaînes ci-dessous sont celles du jeu, telles qu’elles s’affichent.

---

## 1. Cadre

| | |
|---|---|
| Année de départ du joueur | 2026 |
| Passé déjà joué | 1900 → 2026, scénario standard |
| Horizon du modèle | 2100, puis 2150 et 2200 si l’on continue |
| Pas du modèle | 1 an |
| Conseil | tous les 10 ans, à partir de 2030 |
| Fermer le jeu | fige l’année. Le temps n’avance que lorsque les années sont lancées. |

Relancer le modèle reconstruit toute la trajectoire depuis 1900. L’histoire d’avant un cran ne bouge pas. L’avenir, si.

Le filet gris est le scénario sans décision. La couleur est la partie. L’avenir déjà engagé est en pointillé. Le tourner le fait plier, avec du retard.

À l’horizon, s’il n’y a plus rien à faire, la carte de fin s’ouvre. Un cran tenté au-delà affiche `PLUS D'ANNEES`.

---

## 2. Jetons

Chaque conseil donne **3 jetons**. Ils ne se gardent pas d’un conseil à l’autre.

- Chaque niveau d’une orientation coûte un jeton. Plusieurs niveaux d’un coup (molette, boutons, ou glisser du cadran) coûtent autant de jetons que de niveaux franchis.
- Sans jeton, le niveau est refusé. Message : `PLUS DE JETON`.
- Le dilemme ne coûte pas de jeton. Un événement du monde non plus : il n’est pas décidé.
- Les jetons sont dessinés en trois carrés pendant le conseil. Le libellé est `N JETON` s’il en reste un ou zéro, `N JETONS` sinon. Ils flashent ocre quand le conseil les donne.

Au repos, sous le cadran : `UN NIVEAU COUTE UN JETON`.

Pendant un aperçu (cadran encore tenu) : `COUTE N JETON` ou `COUTE N JETONS`.

Quand le niveau est posé, un message ocre dit ce qui change, par exemple `MOINS D'ENFANTS` ou `PLUS A MANGER`.

---

## 3. Les dix orientations

Cinq crans, de 0 à 4. Le cran 0 est le scénario historique. En 2026 le monde standard est déjà au pic : ces crans ne réécrivent pas le passé, ils changent la texture de la chute ou de la tenue.

Une décision est datée de l’année en cours et s’applique à partir de cette année, **avec inertie** : le cran pose une cible, et le paramètre y va en ligne droite depuis sa valeur effective au moment du conseil. Rien ne bascule l’année même : les machines se renouvellent, une norme se diffuse. Un second cran posé avant la fin de la montée repart de la valeur atteinte, pas de la cible. L’aperçu, tant que le doigt tient le cadran, montre l’avenir en ocre sans encore dépenser le jeton. Relâcher engage le niveau.

| Paramètre | Orientation | Années pour le plein effet |
|---|---|---|
| `dcfsn`, plafond à 2 | Familles | 12 |
| `alic`, `tenir` | Usines | 10 |
| `lyf` | Champs | 10 |
| `ppgf` | Fumées | 12 |
| `nruf` | Mines | 12 |
| `fcest` | Écoles | aucune : c’est une date |
| part Services | Services | 5 |
| `icor` | Outils | 12 |
| `cuf` | Conflits | 4 |
| multiplicateur et charge IA | IA | 8 |

Exemple : Outils passé de 0 à 4 en 2030 donne `icor` 3,0 en 2030, 2,4 en 2036, 1,8 à partir de 2042. L’industrie par personne gagne quelques pour cent la première année, pas soixante.

Sous le cadran, deux lignes comparent l’avenir engagé et l’aperçu, à +20 ans et à +50 ans (ou `2100` si l’horizon est plus proche). La ligne retient l’indicateur qui bouge le plus. Si l’écart relatif est infime : `PRESQUE RIEN`.

### 3.1 Familles

Norme de taille de famille, pas le nombre d’enfants réel. Le souhait du modèle est cette norme multipliée par le revenu. Au cran 4, ce produit est plafonné à 2 : il ne remplace pas un souhait déjà plus bas. Courbe liée : population.

Variable World3 : `dcfsn`. Le cran 4 n’utilise pas `zpgt`, qui forcerait le souhait à exactement 2.

| Cran | Valeur affichée |
|---|---|
| 0 | 4.0 norme |
| 1 | 3.5 norme |
| 2 | 3.0 norme |
| 3 | 2.5 norme |
| 4 | 2.0 norme, plafond à 2 |

```
NORME, PAS LE NOMBRE D'ENFANTS.
AU PLUS HAUT, LE SOUHAIT NE PASSE PAS 2.
```

### 3.2 Usines

Combien d’années durent les machines. Plus le cran monte, plus l’investissement neuf est ramené vers le seul remplacement des machines qui meurent : le stock de capital n’augmente plus. Courbe liée : industrie.

Variable World3 : `alic` (durée de vie moyenne du capital industriel, en années). La part `tenir` vaut 0, 0,25, 0,50, 0,75, 1.

| Cran | Valeur affichée |
|---|---|
| 0 | 14 ans |
| 1 | 17 ans |
| 2 | 20 ans |
| 3 | 24 ans |
| 4 | 28 ans |

```
COMBIEN D'ANNEES DURENT LES MACHINES.
PLUS LONGTEMPS. ON CESSE D'EN AJOUTER.
```

### 3.3 Champs

Combien chaque champ produit. Plus de blé, atteint en dix ans. Le sol s’use. Courbe liée : nourriture.

Variable World3 : `lyf` (facteur de rendement des terres).

| Cran | Valeur affichée |
|---|---|
| 0 | 1.0 fois |
| 1 | 1.1 fois |
| 2 | 1.2 fois |
| 3 | 1.6 fois |
| 4 | 2.0 fois |

```
COMBIEN CHAQUE CHAMP PRODUIT.
PLUS DE BLE EN DIX ANS. LE SOL PART.
```

### 3.4 Fumées

Pollution pour chaque objet fait. Moins par objet. L’air sale reste longtemps. Courbe liée : pollution.

Variable World3 : `ppgf` (pollution générée par unité). L’IA multiplie encore ce facteur (voir 3.10).

| Niveau | Valeur affichée |
|---|---|
| 0 | 100 % d'avant |
| 1 | 80 % d'avant |
| 2 | 55 % d'avant |
| 3 | 35 % d'avant |
| 4 | 22 % d'avant |

```
POLLUTION POUR CHAQUE OBJET FAIT.
SI LE METAL ABONDE, LA FAIM PREND LE RELAIS.
```

### 3.5 Mines

Métal tiré par personne. Moins tirer fait durer les mines. Courbe liée : ressources.

Variable World3 : `nruf` (ressources non renouvelables consommées par personne). L’IA multiplie encore ce facteur (voir 3.10).

| Niveau | Valeur affichée |
|---|---|
| 0 | 100 % d'avant |
| 1 | 80 % d'avant |
| 2 | 60 % d'avant |
| 3 | 45 % d'avant |
| 4 | 30 % d'avant |

```
METAL TIRE PAR PERSONNE.
MOINS TIRER FAIT DURER LES MINES.
```

### 3.6 Écoles

L’école retient le souhait d’enfants quand l’industrie tombe. En 2026 le revenu a déjà rendu ce contrôle effectif : le cran ne change presque pas le présent. Courbe liée : population.

Variable World3 : `fcest` (année à partir de laquelle l’école agit sur les naissances). Le niveau 0, année 4000, s’affiche `NON` : l’école ne change rien dans l’horizon du modèle.

| Niveau | Valeur affichée |
|---|---|
| 0 | NON |
| 1 | 2080 |
| 2 | 2060 |
| 3 | 2040 |
| 4 | 2026 |

```
ELLE RETIENT LE SOUHAIT SI L'INDUSTRIE TOMBE.
AUJOURD'HUI, LE REVENU L'A DEJA FAIT.
```

### 3.7 Services

Moins pour les usines neuves, plus pour les soins. La part des champs n’est pas la variable d’ajustement : si la place manque, on réduit l’ajout, pas l’agriculture. Courbe liée : population.

La moitié du cran s’ajoute aux services (`fioas`), l’autre moitié à la consommation (`fioac`). L’industrie neuve reçoit ce qui reste.

| Niveau | Valeur affichée |
|---|---|
| 0 | 0 % |
| 1 | 5 % |
| 2 | 9 % |
| 3 | 14 % |
| 4 | 18 % |

```
MOINS POUR LES USINES NEUVES.
PLUS POUR LES SOINS. LE BLE RESTE.
```

### 3.8 Outils

Moins de machines pour le même objet. L’IA peut encore baisser ce besoin. Courbe liée : industrie.

Variable World3 : `icor` (capital industriel par unité produite). L’IA multiplie encore ce ratio (voir 3.10).

Ce cran règle aussi le nombre de satellites autour de la planète : 8, 16, 28, 44, 64.

| Niveau | Valeur affichée | Unité | Satellites |
|---|---|---|---|
| 0 | 3.0 | par bien | 8 |
| 1 | 2.7 | par bien | 16 |
| 2 | 2.4 | par bien | 28 |
| 3 | 2.1 | par bien | 44 |
| 4 | 1.8 | par bien | 64 |

```
MOINS DE MACHINES POUR LE MEME OBJET.
L'IA PEUT ENCORE BAISSER CE BESOIN.
```

### 3.9 Conflits

Hors des cinq secteurs de World3. Le capital produit moins. Courbe liée : industrie.

Le cran multiplie la part du capital encore au travail (`cuf`). Monter le cran, c’est armer : une part du capital ne produit plus.

| Cran | Valeur affichée |
|---|---|
| 0 | 100 % actif |
| 1 | 95 % actif |
| 2 | 88 % actif |
| 3 | 78 % actif |
| 4 | 65 % actif |

```
HORS DES CINQ SECTEURS DE WORLD3.
PLUS DE CONFLIT : MOINS D'OBJETS FAITS.
```

### 3.10 IA

Hors des cinq secteurs de World3. Plus de production par machine, plus de ressources et de pollution. Courbe liée : industrie.

Le cadran affiche combien de fois les machines font plus d’objets. Le même niveau alourdit en même temps le métal tiré et la pollution. Les deux s’ajoutent aux choix Outils, Mines et Fumées.

À l’écran (plus haut = plus d’objets). Le multiplicateur caché, lui, baisse : moins de machines pour le même objet.

| Niveau | Affiché | Multiplicateur caché |
|---|---|---|
| 0 | X1.0 | 1.00 |
| 1 | X1.1 | 0.92 |
| 2 | X1.2 | 0.84 |
| 3 | X1.3 | 0.76 |
| 4 | X1.5 | 0.68 |

Charge cachée (multiplie à la fois Mines et Fumées) :

| Cran | Ressources et pollution |
|---|---|
| 0 | × 1.00 |
| 1 | × 1.08 |
| 2 | × 1.18 |
| 3 | × 1.30 |
| 4 | × 1.45 |

```
HORS DES CINQ SECTEURS DE WORLD3.
PLUS D'OBJETS, PLUS DE METAL ET D'AIR.
```

### Formules, une fois les crans posés

Pour l’année en cours, le dernier calendrier dont l’année est passée s’applique, chaque paramètre pris à sa valeur effective sur la montée :

- métal par personne = Mines × charge IA
- pollution par objet = Fumées × charge IA
- machines par objet = Outils × multiplicateur IA
- part du capital au travail = calcul World3 × Conflits
- souhait d’enfants = norme × tables de revenu, puis rabattu vers 2 à la force du plafond (0 à 1 sur douze ans) si Familles est au cran 4
- investissement industriel neuf = au plus le remplacement des machines qui meurent, dans la proportion du cran Usines
- part du capital à l’extraction (`fcaor`) = table World3 du métal restant, plus la part détournée par un événement (deep-mining), sans dépasser 95 %

---

## 4. Indicateurs

Cinq sorties du modèle. Population et industrie restent d’une encre neutre : croître n’est pas gagner. Nourriture, pollution et ressources prennent une couleur.

| Clé | Nom court | Libellé complet | Unité | Échelle du graphique |
|---|---|---|---|---|
| pop | POPULATION | NOMBRE DE GENS | milliards, deux décimales, suffixe `MD` | 8 milliards |
| fpc | NOURRITURE | A MANGER PAR PERSONNE | kilogrammes, entier, suffixe `KG` | 1 000 |
| iopc | INDUSTRIE | OBJETS FAITS PAR PERSONNE | entier, sans unité | 500 |
| ppolx | POLLUTION | POLLUTION | un décimal, sans unité | 16 |
| nrfr | RESSOURCES | METAL QU'IL RESTE | pourcent, suffixe `%` | 100 % |

Couleur d’un chiffre :

| Indicateur | Vert | Ocre | Rouille |
|---|---|---|---|
| Nourriture | au moins 420 kg | de 300 à 419 kg | moins de 300 kg |
| Pollution | moins de 6 | de 6 à 9,9 | 10 ou plus |
| Ressources | 40 % ou plus | de 20 % à 39 % | moins de 20 % |
| Population, industrie | encre neutre | | |

---

## 5. Le mot du monde

Un seul mot, calculé sur les sorties réelles, en comparant l’année lue à cinq ans plus tôt.

Pente de population = variation relative sur ces cinq ans, ramenée à une année.

Le mot est choisi dans cet ordre. Le premier qui s’applique gagne.

1. **CROISSANCE** — avant 1990, population qui ne baisse pas, nourriture au moins 280 kg, pollution sous 8.
2. **FAMINE** — nourriture sous 300 kg, ou industrie sous 45 et nourriture sous 400 kg. C’est le scénario sans décision.
3. **STABLE** — nourriture au moins 420 kg, industrie au moins 130 et qui ne perd pas plus de 1,2 % par an, pollution sous 6, ressources au moins 22 %, population qui ne monte pas de plus de 0,35 % par an et ne descend pas de plus de 1 % par an. Une descente lente avec assez à manger compte. Un monde dont les usines fondent n’est pas stable, même si l’on mange.
4. **RALENTISSEMENT** — nourriture au moins 420 kg, industrie au moins 80, pollution sous 8, ressources au moins 18 %, population qui ne chute pas plus vite que 1,6 % par an. Une descente où l’on mange encore.
5. **CROISSANCE** — population qui monte (plus de 0,2 % par an), nourriture au moins 380 kg, pollution sous 8.
6. **CRISE** — pollution à 10 ou plus, ou ressources sous 20 %, ou nourriture sous 380 kg.
7. **TENSION** — tout le reste.

Couleurs du mot : `CROISSANCE` en encre, `STABLE` et `RALENTISSEMENT` en vert, `TENSION` en ocre, `CRISE` et `FAMINE` en rouille.

Scénario sans décision, tel que le jeu le nomme : 1970 `CROISSANCE`, 2026 `TENSION`, 2050 `FAMINE`.

L’oracle du monde regarde vingt ans devant (borné à 2100) et donne le mot de cette année-là. S’il reste moins d’un an avant 2100, il affiche `C'EST FINI` puis `2100`. Sinon : `DANS N ANS` puis le mot.

En bas à gauche, alignée sur le bouton, une phrase tourne toutes les 3 secondes, de la couleur du mot. Elle dit ce qui presse (`ON MANQUE A MANGER`, `L'AIR EST TROP SALE`, `LES MINES SONT VIDES`, ou le palier d’avant), le plus gros mouvement sur cinq ans (`ON MANGE MOINS`, `PLUS DE POLLUTION`, `MOINS DE METAL`…), et l’année du prochain choix : `CHOIX EN 2030`.

Au repos, la planète tourne déjà. Plus le mot est grave, plus elle tourne vite. Un tour lui donne une impulsion. Les satellites accélèrent quand le niveau d’IA monte. L’atmosphère s’épaissit et rouille avec la pollution.

---

## 6. Un tour

`AVANCER` joue cinq ans, sans dépasser 2100.

S’il reste un conseil non tranché dont l’année tombe dans ces cinq ans, le tour s’interrompt sur ce conseil. Le plus tôt l’emporte. Le choix est daté de l’année du conseil, puis le tour s’achève jusqu’à la cible.

Un événement du monde peut tomber dans les mêmes cinq ans (voir section 7). S’il est plus tôt que le conseil, sa carte passe d’abord. Il ne coûte pas de jeton. Il s’applique à son année, puis les années reprennent : la Terre tourne jusqu’au prochain événement ou jusqu’au conseil.

Après le saut :

- l’année avance ;
- un jeton est rendu si le joueur en a moins de cinq ;
- un écran récapitule ce qui a passé.

Cet écran s’intitule `1 AN A PASSE` ou `N ANS ONT PASSE`. Si un événement est tombé dans ces années, son titre s’écrit en ocre dessous.

Si le mot n’a pas changé : `PAREIL`, puis le mot. S’il a changé : l’ancien mot, `>`, le nouveau.

Puis une phrase ocre sur le plus gros changement, par exemple `ON MANGE MOINS` ou `MOINS D'OBJETS`. Si presque rien n’a bougé : `PRESQUE RIEN N'A BOUGE`.

Puis les cinq indicateurs, valeur d’avant `>` valeur d’après. Bouton : `CONTINUER`.

S’il reste un conseil dont l’année est déjà atteinte, il s’ouvre après ce récapitulatif. Hors d’un tour en cours, ce choix est daté de l’année présente.

---

## 7. Les événements du monde

Vingt-quatre événements. Ils ne sont pas des choix. À chaque tour, **deux chances sur cinq** qu’un événement encore inédit tombe. Un seul par tour. Une fois arrivé, il ne revient pas. Une partie en voit en général cinq ou six.

L’année est tirée dans le tour, plutôt vers le milieu, et écartée de l’année d’un conseil. La carte s’interrompt là. En haut, un cadre ocre : `EVENEMENT`. Puis l’année, le titre, ce qui arrive, et la conséquence en ocre. En bas : `LE MONDE DECIDE`. Bouton : `CONTINUER`. Échap continue aussi : l’événement a déjà lieu. `CONTINUER` reprend la rotation tout de suite, jusqu’au prochain événement ou jusqu’au conseil.

Le tirage ne dépend que d’une graine enregistrée, de l’année du tour et des événements déjà tombés. Recharger avant d’avoir continué redonne la même carte. Une nouvelle partie refait un tirage.

L’effet part de l’année de l’événement et dure. Les multiplicateurs **montent en puissance** sur un nombre d’années propre à chaque carte (`ramp`) : rien l’année même, tout au bout de la montée, en ligne droite. Une technique se déploie, un accord s’applique peu à peu. Un choc de stock (gens, métal, terres, usines, pollution) ne frappe qu’une fois, l’année du franchissement, quel que soit `ramp`. Le métal découvert (`nri_add`) arrive au prorata des années de la montée. Le trait gris n’inclut pas ces événements : c’est le scénario sans décision. La couleur, si.

| Montée | Cartes |
|---|---|
| 0 an (plein effet l’année même) | Pandémie, Grande guerre, Sécheresse, Filon mort, L’accident, Le krach, L’érosion, L’ISS |
| 3 ans | La paix, Le vaccin |
| 5 ans | Baby-boom, Charbon |
| 6 ans | L’IAG, Jetable |
| 8 ans | L’accord, Médecine, Insectes, Barrages |
| 10 ans | Le climat, Gisement, Les écoles, Recyclage, Batteries, Mines lointaines |
| 15 ans | La fusion, Deep-mining |

Un événement peut aussi détourner une part du capital industriel vers l’extraction (`fcaor_add`, ajoutée à la table World3, plafonnée à 95 %). Elle monte avec la même rampe.

Sous le globe, une phrase de l’événement tourne encore douze ans. Le récapitulatif du tour reprend le titre, en ocre.

Les multiplicateurs s’empilent s’il en tombe plusieurs au fil de la partie, dans des bornes : le rendement des terres reste entre 0,45 et 2,4, la pollution générée entre 0,20 et 3, le métal tiré entre 0,15 et 3, la durée des machines entre 8 et 40 ans, le capital par objet entre 0,90 et 6, la part des usines au travail entre 0,35 et 1, les enfants voulus entre 1,6 et 6,5, les morts entre 0,55 et 1,5 fois.

### L'IAG

```
LES MACHINES PENSENT SEULES.
PLUS D'OBJETS. PLUS DE METAL.
```

`PLUS D'OBJETS, PLUS DE DEGATS`. Les machines produisent plus (`icor` × 0,70). Elles tirent plus de métal (`nruf` × 1,42) et salissent plus (`ppgf` × 1,30). Tout de suite, plus d’objets. Ensuite, les mines baissent et l’air monte.

### LA FUSION

```
LES CENTRALES A FUSION TOURNENT.
ON USE MOINS DE METAL.
```

`MOINS DE METAL, MOINS D'AIR SALE`. `nruf` × 0,55, `ppgf` × 0,70.

### PANDEMIE

```
UN MAL NOUVEAU TRAVERSE LES VILLES.
BEAUCOUP DE GENS MEURENT.
```

`LA POPULATION BAISSE D'UN COUP`. Cette année-là, il reste 88 % des gens.

### LE CLIMAT

```
LES SAISONS CASSENT.
LES CHAMPS RENDENT MOINS.
```

`MOINS DE BLE, DES TERRES PERDUES`. Rendement × 0,78. Il reste 94 % des terres cultivées.

### GRANDE GUERRE

```
DES ARMEES SE BATTENT PARTOUT.
DES USINES BRULENT.
```

`MOINS D'USINES, MOINS DE GENS`. Il reste 95 % des gens, 86 % des usines, et 76 % des usines encore au travail.

### LA PAIX

```
LES CANONS SE TAISENT.
ON REFAIT DURER LES MACHINES.
```

`LES USINES REPRENNENT`. Part au travail × 1,22 (sans dépasser 100 %). Les machines durent × 1,15.

### SECHERESSE

```
LA PLUIE MANQUE PLUSIEURS ANNEES.
LE BLE BAISSE.
```

`MOINS A MANGER`. Rendement × 0,82.

### GISEMENT

```
ON TROUVE UN GRAND FILON.
LES MINES OUVRENT EN DIX ANS.
```

`UN PEU PLUS DE METAL, PEU A PEU`. Le stock exploitable augmente de 8 % du stock d’origine, étalé sur dix ans. En 2030, cela tient le métal restant à 28 % jusqu’en 2040 au lieu de 23 %, et l’industrie à 180 au lieu de 139. Un seul filon ne refait pas le monde.

### FILON MORT

```
UNE GRANDE MINE SE FERME.
LE METAL RESTANT BAISSE.
```

`MOINS DE METAL D'UN COUP`. Le métal restant × 0,80.

### L'ACCORD

```
LES PAYS S'ENTENDENT.
CHAQUE OBJET SALIT MOINS.
```

`MOINS DE POLLUTION`. `ppgf` × 0,64.

### L'ACCIDENT

```
UNE USINE LACHE UN POISON.
L'AIR RESTE SALE LONGTEMPS.
```

`UN PIC DE POLLUTION`. La pollution monte d’environ 1,5 (indice 1970), puis chaque objet salit × 1,15.

### LES ECOLES

```
PRESQUE TOUS LES ENFANTS
VONT MAINTENANT A L'ECOLE.
```

`MOINS D'ENFANTS, PLUS TARD`. Enfants voulus × 0,84.

### BABY-BOOM

```
ON VEUT DE NOUVEAU
BEAUCOUP D'ENFANTS.
```

`PLUS DE NAISSANCES`. Enfants voulus × 1,16.

### MEDECINE

```
ON MEURT MOINS TOT.
LES VIEUX RESTENT PLUS.
```

`MOINS DE MORTS`. Morts × 0,75.

### INSECTES

```
MOINS DE POLLINISATEURS.
LES CHAMPS RENDENT MOINS.
```

`MOINS DE BLE`. Rendement × 0,80.

### RECYCLAGE

```
ON REFAIT LES OBJETS
AVEC L'ANCIEN METAL.
```

`ON TIRE MOINS DE METAL`. `nruf` × 0,66.

### LE KRACH

```
L'ARGENT SE FIGE.
DES USINES S'ARRETENT.
```

`MOINS D'OBJETS FAITS`. Part au travail × 0,76. Il faut plus de machines par objet (`icor` × 1,16).

### BARRAGES

```
L'EAU ARRIVE AUX CHAMPS SECS.
CHAQUE CHAMP PRODUIT PLUS.
```

`PLUS DE BLE`. Rendement × 1,18.

### CHARBON

```
LE CHARBON REDEVIENT PAS CHER.
L'AIR SE SALIT DAVANTAGE.
```

`PLUS D'OBJETS, PLUS D'AIR SALE`. `ppgf` × 1,40. Moins de machines par objet (`icor` × 0,88).

### BATTERIES

```
ON STOCKE LE COURANT.
L'ENERGIE USE MOINS DE METAL.
```

`MOINS DE MINES, AIR PLUS CLAIR`. `nruf` × 0,78, `ppgf` × 0,80.

### L'EROSION

```
L'EAU EMPORTE LA TERRE.
DES CHAMPS DISPARAISSENT.
```

`MOINS DE TERRES ET DE BLE`. Il reste 91 % des terres. Rendement × 0,88.

### LE VACCIN

```
UN VACCIN ARRETE DES MAUX.
ON MEURT MOINS.
```

`MOINS DE MORTS`. Morts × 0,84.

### MINES LOINTAINES

```
ON RAPPORTE DU METAL.
LES MINES D'ICI SOUFFLENT.
```

`ON TIRE MOINS ICI`. `nruf` × 0,70.

### JETABLE

```
LES OBJETS CASSENT PLUS VITE.
IL EN FAUT SANS CESSE.
```

`LES MACHINES DURENT MOINS`. Durée de vie × 0,74.

---

## 8. Les conseils

Sept conseils, de 2030 à 2090, tous les dix ans. Chacun pose les deux dilemmes de la décennie, l’un après l’autre. En haut de la carte, un cadre : `DILEMME`. La réponse déplace d’un niveau le choix indiqué, bornée entre 0 et 4. Si le niveau est déjà au bout, le conseil est quand même consommé : il ne reviendra pas.

Un conseil déjà tranché ne revient pas, même après un retour en arrière d’année (le jeu n’en propose pas). Une nouvelle partie les rouvre tous.

Cinq conseils (2055, 2065, 2075, 2085, 2095) ne s’ouvrent que si le tour franchit leur année. Une partie déjà au-delà ne les rattrape pas.

Les réponses gratuites qui tiennent en 2026 vont aux mines, aux fumées, à un cran modéré de champs, et au plafond sur les enfants. Aucune ne rallonge les usines.

### 2030 — LE METAL

```
LE METAL VA MANQUER.
UN FILON NEUF, OU EN TIRER MOINS.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | DEEP-MINING | événement Deep-mining | | PLUS DE METAL, LENTEMENT. CA COUTE |
| B | GARDER | Mines | +1 | MOINS DE METAL PAR PERSONNE |

Deep-mining : le stock exploitable augmente d’un cinquième du stock d’origine, étalé sur quinze ans, et 8 % du capital industriel part creuser au lieu de produire (`fcaor_add` 0,08, même rampe). En 2030, l’industrie par personne gagne 3 % la première année, tient autour de 190 jusqu’en 2040 (139 sans), puis redescend ; le métal restant culmine à 33 % vers 2045 au lieu de 21 %. La pollution reste un peu plus haute et plus longtemps. Fumées au cran 4 la rattrape. Avant ce réglage, le stock doublait d’un coup et l’industrie faisait × 2 l’année même : c’était la table World3 `fcaor` qui lâchait l’extraction d’un seul coup.

### 2035 — LES USINES

```
LES USINES VEULENT GRANDIR.
GARDER LE METAL, OU ALLER VITE.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | GARDER | Mines | +1 | MOINS DE METAL PAR PERSONNE |
| B | VITE | IA | +1 | PLUS D'OBJETS, PLUS DE DEGATS |

### 2040 — L'AIR

```
L'AIR SALE ABIME LES TERRES.
FILTRER, OU POUSSER LES CHAMPS.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | FILTRER | Fumées | +1 | MOINS DE POISON PAR OBJET |
| B | CHAMPS | Champs | +1 | PLUS DE BLE. LE SOL S'USE |

### 2045 — L'IA

```
L'IA FAIT TOURNER LES USINES.
ELLE POLLUE ET CREUSE AUSSI.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | FREINER | IA | −1 | ON GARDE LE RYTHME D'AVANT |
| B | PLUS VITE | IA | +1 | PLUS D'OBJETS, PLUS DE DEGATS |

### 2050 — LE METAL

```
LE METAL DEVIENT CHER.
EN GARDER, OU CREUSER PLUS.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | GARDER | Mines | +1 | MOINS DE METAL PAR PERSONNE |
| B | CREUSER | Mines | −1 | ON VIDE LES MINES PLUS VITE |

### 2055 — L'ASSIETTE

```
ON MANGE MOINS BIEN.
MOINS D'ENFANTS, OU PLUS DE CHAMPS.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | ENFANTS | Familles | +1 | MOINS DE BOUCHES, PLUS TARD |
| B | CHAMPS | Champs | +1 | PLUS DE BLE. LE SOL S'USE |

### 2060 — LES GENS

```
LES GENS RESTENT TROP NOMBREUX.
VISER DEUX, OU REMETTRE A PLUS TARD.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | DEUX | Familles | +1 | MOINS D'ENFANTS VOULUS |
| B | PLUS TARD | Familles | −1 | PLUS D'ENFANTS MAINTENANT |

### 2065 — L'ECOLE

```
LE SOUHAIT TIENT ENCORE
SI L'INDUSTRIE TOMBE.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | OUVRIR | Écoles | +1 | L'ECOLE AGIT PLUS TOT |
| B | ATTENDRE | Écoles | −1 | ON LAISSE POUR PLUS TARD |

### 2070 — LE SOL

```
LE SOL SE FATIGUE.
ON LUI EN DEMANDE TROP.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | REPOS | Champs | −1 | LES CHAMPS SOUFFLENT |
| B | FORCER | Champs | +1 | PLUS DE BLE, MOINS DE SOL |

### 2075 — L'USURE

```
LES USINES TOURNENT ENCORE.
FILTRER L'AIR, OU ALLER VITE.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | FILTRER | Fumées | +1 | MOINS DE POISON PAR OBJET |
| B | VITE | IA | +1 | PLUS VITE, PLUS DE DEGATS |

### 2080 — APRES NOUS

```
LES ENFANTS D'AUJOURD'HUI
VERRONT ENCORE L'AN 2100.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | AIR | Fumées | +1 | MOINS DE POLLUTION POUR EUX |
| B | ENFANTS | Familles | −1 | PLUS D'ENFANTS MAINTENANT |

### 2085 — LES SOINS

```
LE BLE ET LES SOINS,
OU ENCORE DES USINES.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | PARTAGER | Services | +1 | MOINS D'USINES NEUVES |
| B | USINES | Services | −1 | ON GARDE POUR PRODUIRE |

### 2090 — AVANT LA FIN

```
DERNIER GRAND CHOIX
AVANT L'AN 2100.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | GARDER | Mines | +1 | MOINS DE METAL PAR PERSONNE |
| B | VIDER | Mines | −1 | ON PREND LE METAL RESTANT |

### 2095 — LA FIN

```
IL RESTE PEU D'ANNEES.
POLLUER MOINS, OU PRODUIRE ENCORE.
```

| | Bouton | Loi | Niveau | Sous-texte |
|---|---|---|---|---|
| A | AIR | Fumées | +1 | MOINS DE POLLUTION PAR OBJET |
| B | PRODUIRE | IA | +1 | PLUS D'OBJETS, PLUS DE DEGATS |

---

## 9. La planète

La sphère est un dessin, pas un climat. World3 ne calcule pas la température. Les calottes sont une carte : au-delà de 78° nord, en deçà de 68° sud, et le Groenland.

La couleur suit quatre sorties :

- **Sol.** Vert mousse quand on mange. Il tire vers l’ocre à mesure que la nourriture s’éloigne de 500 kg (plein ocre vers 160 kg). La pollution le rouille ensuite, jusqu’à 55 % de rouille quand la pollution vaut 16.
- **Mer.** Bleue, puis plus sombre avec la pollution.
- **Côtes.** Sable, au contact de la terre.
- **Villes.** Une grille fixe, plus dense quand la population monte. Entre 1,4 et 7,9 milliards, la part de terres allumées passe de 0 à 22 %. Les lumières ne s’allument que sur la face sombre.
- **Balafres.** Quand il reste moins de 55 % des ressources, des terres virent au brun. Plus le filon est vide, plus il y en a.
- **Atmosphère.** Un dégradé en aplats, du même grain que le globe, collé au limbe. L’air clair est un fin liseré bleu, presque transparent. Il s’épaissit jusqu’à l’anneau des années, s’opacifie et passe par l’ocre jusqu’à la rouille : l’effet est plein quand la pollution vaut 16.
- **Anneau de points.** La fraction allumée est le chemin parcouru de 2026 à 2100. Il passe à l’ocre l’instant où l’année vient de sauter.
- **Satellites.** Leur nombre suit le niveau Outils (8, 16, 28, 44, 64). Ils vont plus vite quand le niveau d’IA monte.

`GLISSEZ LA PLANETE POUR LA TOURNER.` est écrit sur l’écran Temps. En bas à gauche, alignée sur le bouton, c’est la phrase du monde qui tourne.

---

## 10. Écrans

Quatre boutons, toujours en bas. `MONDE` `CHOIX` `COURBES` se partagent la gauche. À droite, un carré avec une roue crantée ouvre l’écran du temps. Touches `1` `2` `3` `4`.

Quatre cartes précèdent le monde, au premier lancement et à chaque nouvelle partie.

### Calcul, à l’ouverture

```
WORLD3
DE 1900 A 2100
```

### Intro

Carte 1, bouton `SUIVANT` :

```
WORLD3

FACE AUX BOULEVERSEMENTS,
VOUS ETES TIRE AU SORT
PARMI TOUS LES HUMAINS.
```

Carte 2, bouton `SUIVANT` :

```
L'AVENIR

VOUS DECIDEZ DES GRANDES
ORIENTATIONS DU FUTUR.
TOUS LES 5 ANS, VOUS TRANCHEZ
VERS UN FUTUR PLUS STABLE.
```

Carte 3, bouton `SUIVANT` :

```
LE TEMPS

UN TOUR = 5 ANS.
FERMER LE JEU ARRETE LE TEMPS.
UN TOUR REND UN JETON.
```

Carte 4, bouton `COMMENCER` :

```
LE NIVEAU

LE FUTUR EST EN POINTILLE.
UN NIVEAU COUTE UN JETON.
LA PLANETE REPOND PLUS TARD.
```

### Monde

- L’année, en grand.
- Les jetons.
- Le mot du présent.
- La phrase qui tourne, en bas à gauche, alignée sur le bouton.
- `AVANCER`, ou `FIN 2100` si 2100 est atteint.
- L’oracle : `DANS N ANS` et le mot, ou `C'EST FINI` / `2100`.
- Les cinq indicateurs de l’année en cours.

### Choix

- Année, jetons, `JETON` ou `JETONS`.
- Flèches `<` et `>` pour changer de choix. Un glissé horizontal sur la carte (pas sur le cadran) fait de même.
- Titre et deux lignes d’indice.
- Cadran : la valeur, l’unité, cinq niveaux. Boutons `+` et `-`.
- Mini-courbe de la série liée au choix : trait gris si l’on ne change rien, passé en trait plein, avenir en pointillé, présent en trait ocre. L’aperçu non encore payé se dessine en ocre plein.
- `1 JETON PAR NIVEAU` / `UN TOUR REND UN JETON`, ou le coût et les deux horizons pendant l’aperçu.
- Dix points en bas, un par choix.

Glisser le cadran vers le haut ou la droite monte le niveau. Le geste s’arrête au nombre de jetons restants et affiche `PLUS DE JETON`.

### Courbes

Cinq pastilles, toutes allumées au départ. Les toucher les montre ou les cache. Si aucune n’est allumée : `CHOISIR UNE COURBE`.

Légende sur le graphique :

```
GRIS = SANS VOUS
POINTILLE = PLUS TARD
```

Repères d’années : `1900`, `1950`, `2000`, `2050`, `2100`.

Toucher le graphique épingle une année. La molette la déplace de deux ans. Le mot et les chiffres sont ceux de l’année lue.

- `MAINTENANT` si l’année lue est le présent.
- `PASSE` si elle est derrière.
- `PLUS TARD` si elle est devant.

`SUIVRE` revient au présent. Le bouton n’apparaît que lorsqu’une année est épinglée.

### Temps

```
UN TOUR VAUT
5 ANS
```

Puis `AVANCER` ou `FIN 2100`.

Son : `AVEC SON` ou `SANS SON`. Des clics d’interface calculés par le jeu, secs, courts et légers. Chaque geste a le sien. Déplacer l’année du graphique fait un cran à peine plus aigu vers 2100. Faire défiler les choix fait un souffle léger. Le cadran claque selon le niveau, un peu plus haut, sans faire une mélodie. Les onglets, les pastilles, les boutons et le refus ne partagent pas le même son. Le tour est deux crans secs. Il est allumé par défaut. Une nouvelle partie le conserve.

Règles écrites sur cet écran :

```
FERMER LE JEU ARRETE LE TEMPS.
UN NIVEAU COUTE UN JETON. UN TOUR EN REND UN.
LE FUTUR EST EN POINTILLE. L'EFFET ARRIVE PLUS TARD.
PARFOIS LE MONDE BOUGE SANS VOUS.
GLISSEZ LA PLANETE POUR LA TOURNER.
CHIFFRES DE WORLD3, MEADOWS 1972. MOTEUR PYWORLD3.
1 MONDE   2 CHOIX   3 COURBES   4 ROUE
```

`NOUVELLE PARTIE` ouvre :

```
OUBLIER CETTE
PLANETE ?

ON RECOMMENCE EN 2026.
```

`GARDER` revient. `OUBLIER` remet 2026, trois jetons, tous les niveaux à zéro, les conseils rouverts, les événements effacés, une nouvelle graine, et rejoue l’intro. Le son reste comme il était.

### Messages brefs

| Situation | Texte |
|---|---|
| Niveau sans jeton | PLUS DE JETON |
| Loi alors que 2100 est atteint | PLUS D'ANNEES |

Échap ferme la carte du moment (intro : avance ; récapitulatif : continue ; événement du monde : continue ; oubli : garde). Sans carte, Échap quitte. Quitter enregistre la partie.

---

## 11. Commandes

| Geste | Monde | Choix | Courbes | Temps |
|---|---|---|---|---|
| Glisser | tourne la planète, dans tous les sens | sur le cadran, change le niveau ; ailleurs, change de choix | épingle et lit une année | — |
| Molette | tourne le lacet | un cran | lit deux ans plus tôt ou plus tard | — |
| Flèches | tournent la planète | gauche / droite : le choix ; haut / bas : le niveau | tournent la planète | tournent la planète |
| Touches 1 2 3 4 | Monde, Choix, Courbes, Temps | | | |

La fenêtre logique fait 720×720. `python main.py --scale 2` l’agrandit. `python main.py --fullscreen` la passe en plein écran (prévu pour un Raspberry Pi Zero 2W). Le tactile est vu comme une souris.

---

## 12. Partie sauve

Fichier `save.json`, à côté de `main.py`. Le jeu écrit tout seul, deux secondes après un changement, et encore en quittant.

Ce qui est gardé : l’année, les jetons, le calendrier des niveaux (année + dix valeurs), l’intro déjà vue, les conseils tranchés, les événements déjà tombés (année + identifiant), la graine du tirage, le son.

Au chargement, l’année est ramenée entre 2026 et 2100, les jetons entre 0 et 3, chaque niveau entre 0 et 4. S’il manque le point de départ de 1900, il est remis : dix niveaux à zéro.
