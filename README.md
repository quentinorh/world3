# WORLD3

Un kiosque pour penser le futur. Au démarrage, un menu ouvre plusieurs applications sur le même écran. Aujourd'hui : le jeu WORLD3, le globe RELIEF, la carte CARTE, le lecteur SP2050 et le jardin JARDIN. D'autres suivront.

Sur un ordinateur, le menu s'ouvre dans une fenêtre. Sur un Raspberry Pi 3 B+, il tient une dalle tactile de 720×720, sans bureau.

## Applications

**WORLD3** reprend le modèle [World3](https://github.com/cvanwynsberghe/pyworld3) de Meadows, Meadows et Randers : population, industrie, agriculture, pollution, ressources. On arrive en 2026. Le passé, de 1900 à aujourd'hui, est déjà joué.

Tous les dix ans, le conseil de l'humanité. Trois jetons pour les orientations, puis les dilemmes de la décennie. Entre deux conseils, les années défilent. Un événement peut survenir, environ deux fois tous les dix ans, jamais plus de trois entre deux conseils. Le bouton i explique le sujet. En 2100, s'il n'y a plus rien à faire, un mot pédagogique. Si le monde tient, on peut continuer. Les règles sont dans `REGLES.md`.

**RELIEF** montre le relief de la Terre. Un doigt tourne le globe, `+` et `-` zooment. Un curseur déplace le niveau des mers entre −140 m et +80 m. Une terre basse n'est couverte que si l'eau y arrive depuis l'océan : la Caspienne reste à sec. Le terrain est celui d'aujourd'hui, calottes comprises.

**CARTE** montre OpenStreetMap hors ligne : côtes, villes, forêts, routes. Un doigt déplace la carte, `+` et `-` zooment. La préparation se fait une fois, sur l'ordinateur :

```bash
python -m carte.fetch
```

Le fichier, de l'ordre de 4 Go, va dans `var/carte/`. Le Pi ne télécharge pas la planète.

**JARDIN** génère un jardin de plantes imaginaires, fluorescentes, et on y avance lentement. L'axe Y du capteur d'inclinaison regarde à gauche et à droite. `RÉGLAGES` change l'espèce, la graine, les passes, l'angle, la densité, le tropisme et l'heure du ciel, entre l'aube et le couchant.

**SP2050** lit les futurs publics de [sp2050.org/futurs](https://sp2050.org/futurs). S'il y a Internet, les textes et les couvertures sont copiés dans `var/sp2050/` et restent lisibles hors ligne. À la main : `python -m sp2050.sync`.

## Ordinateur

```bash
python -m pip install -r requirements.txt
python main.py
```

Fenêtre plus grande : `python main.py --scale 2`.

Une application seule : `python -m world3`, `python -m relief`, `python -m carte`, `python -m sp2050`, `python -m jardin`.

## Raspberry Pi 3 B+

Écran Waveshare 4inch HDMI LCD (C), 720×720. Système : Raspberry Pi OS Lite 32 bits (Debian Trixie). Pas de bureau : le menu s'affiche en plein écran, directement sur la dalle. La maison ramène au menu. Échap fait de même depuis le globe du jeu, RELIEF, la carte et le jardin (dans le jardin, Échap ferme d'abord les réglages). Un coin du menu éteint le Pi.

Depuis Windows, après le premier démarrage du Pi (SSH et Wi-Fi réglés dans Raspberry Pi Imager, nom d'hôte `world3`) :

```powershell
copy deploy\target.example.ps1 deploy\target.ps1
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -InstallKey
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -Setup
```

`-InstallKey` sert si l'Imager a activé SSH par mot de passe. Si la clé publique est déjà dans l'image, cette étape se saute.

Les fois suivantes, le même script sans `-Setup` envoie le code et relance le menu. La partie (`save.json`), les futurs SP2050 et la carte déjà sur le Pi ne sont pas effacés. La carte (`var/carte/terre.pmtiles`) est envoyée si elle est déjà sur l'ordinateur. Le détail est en tête de `deploy\deploy.ps1`.

Sur le Pi, le service `world3` tient l'écran. `sudo systemctl stop world3` le laisse libre. Le tactile est vu comme une souris.

Si GitHub répond, un bouton du menu met le kiosque à jour et relance le service. La partie, `var/` et l'environnement Python restent.

Capteur d'inclinaison optionnel (DFRobot BMA220) : VCC sur 3,3 V (pas 5 V), GND, SDA sur GPIO2 (broche 3), SCL sur GPIO3 (broche 5), INT non branché. Le bus I2C est déjà activé par `-Setup`. Diag : `python -m device.accel`. Sur le globe du jeu, l'axe Y du capteur décale le point de vue, sans inertie ni arrêt de la rotation de repos. Le doigt ne tourne qu'à l'horizontal. Dans le jardin, le même axe regarde à gauche et à droite pendant la marche. Sans capteur, haut et bas du clavier le remplacent.

`-Setup` ajoute aussi un minuteur, `sp2050-sync.timer`, qui reprend les futurs au démarrage et toutes les six heures dès que le réseau est là.

## Jouer

Dans WORLD3 :

- 2026 : le globe, l'année, les chiffres, trois petits boutons (réglages, courbes, pause).
- Le grand bouton nomme le prochain conseil, par exemple `2030 - PROCHAIN CONSEIL >`.
- Les années et les chiffres défilent. La Terre tourne. Un événement peut s'arrêter au passage. `CONTINUER`, comme le choix d'un dilemme, ramène à la planète et au bouton du conseil suivant.
- Au conseil : trois jetons pour les orientations, puis un dilemme. Le bouton i ouvre la fiche.
- Pause : la Terre tourne, on peut la faire glisser, l'année, et `PLAY`.
- Échap ferme une fiche, ou quitte le jeu depuis le globe.

Éditeur des cartes, à part :

```bash
python -m world3.editor
```

Il écrit `contenu.json`. Relancer le jeu pour lire les textes.

La partie est dans `save.json`, à côté de `main.py`.

## Crédits

Les chiffres du jeu viennent de World3. Les équations sont celles de 1972. Le récit des scénarios reprend aussi les livres de 1992 et de 2004. Donella H. Meadows, Dennis L. Meadows, Jørgen Randers, William W. Behrens, *The Limits to Growth*, 1972. Dennis L. Meadows et al., *Dynamics of Growth in a Finite World*, 1974.

Moteur : [PyWorld3](https://github.com/cvanwynsberghe/pyworld3), Charles Vanwynsberghe, licence CeCILL 2.1. Ce dépôt appelle la bibliothèque, il ne la recopie pas.

Sons : le jeu les calcule. Clics secs, courts, légers.

La planète du jeu est un dessin. Ses couleurs suivent la nourriture, la pollution, la population et les ressources restantes. Les calottes y sont une carte, pas une température : World3 ne calcule pas le climat.

Le relief vient d'ETOPO1 (NOAA, domaine public). La carte est un extrait OpenStreetMap via Protomaps ; l'écran porte `© OpenStreetMap`. SP2050 reprend les futurs publics de [sp2050.org](https://sp2050.org/futurs). Le jardin reprend les grammaires de Lindenmayer : une chaîne de symboles, réécrite, puis lue par une tortue dans l'espace.
