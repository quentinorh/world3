# WORLD3

Un petit jeu sur le modele [World3](https://github.com/cvanwynsberghe/pyworld3) de Meadows, Meadows et Randers : population, industrie, agriculture, pollution, ressources. Vous arrivez en 2026. Le passe, de 1900 a aujourd'hui, est deja joue.

Tous les dix ans, le conseil de l'humanite. Vous etes seuls a decider des orientations (trois jetons) et des dilemmes de la decennie. Entre deux conseils, les annees defilent. Un evenement peut survenir, environ deux fois tous les dix ans, jamais plus de trois entre deux conseils. Le bouton i explique le sujet. En 2100, s'il n'y a plus rien a faire, un mot pedagogique. Si le monde tient, on peut continuer.

## Ordinateur

```bash
python -m pip install -r requirements.txt
python main.py
```

Fenetre plus grande : `python main.py --scale 2`.

Le menu propose WORLD3, RELIEF, CARTE et SP2050. RELIEF montre le relief de la Terre et un curseur pour le niveau des mers. CARTE montre OpenStreetMap hors ligne. La preparation, une fois, sur l'ordinateur : `python -m carte.fetch` (environ 4 Go dans `var/carte/`). SP2050 lit les futurs de sp2050.org. Au lancement, s'il y a Internet, les textes sont copies dans `var/sp2050/` et restent lisibles hors ligne. A la main : `python -m sp2050.sync`.

Le jeu seul : `python -m world3`. Le globe seul : `python -m relief`. La carte seule : `python -m carte`. Le lecteur seul : `python -m sp2050`.

## Raspberry Pi 3 B+

Ecran Waveshare 4inch HDMI LCD (C), 720x720. Systeme : Raspberry Pi OS Lite 32 bits (Debian Trixie). Pas de bureau : le menu affiche en plein ecran par SDL, directement sur la dalle. WORLD3, RELIEF, CARTE et SP2050 s'ouvrent depuis la. Echap, sur le globe ou la carte, revient au menu. Un coin du menu eteint le Pi.

Depuis Windows, apres le premier demarrage du Pi (SSH et Wi-Fi regles dans Raspberry Pi Imager, nom d'hote `world3`) :

```powershell
copy deploy\target.example.ps1 deploy\target.ps1
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -InstallKey
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -Setup
```

`-InstallKey` sert si l'Imager a active SSH par mot de passe. Si la cle publique est deja dans l'image, cette etape se saute.

Les fois suivantes, le meme script sans `-Setup` envoie le code et relance le menu. La sauvegarde deja sur le Pi (`save.json`) n'est pas ecrasee, ni les textes SP2050. La carte (`var/carte/terre.pmtiles`) est envoyee si elle est deja sur l'ordinateur, et n'est pas effacee sinon. Le detail est en tete de `deploy\deploy.ps1`.

Sur la carte, le service `world3` tient l'ecran. `sudo systemctl stop world3` le laisse libre. Le tactile, interrupteur au dos sur I2C, est vu comme une souris.

Capteur d'inclinaison optionnel (DFRobot BMA220) : VCC sur 3,3 V (pas 5 V), GND, SDA sur GPIO2 (broche 3), SCL sur GPIO3 (broche 5), INT non branche. Le bus I2C est deja active par `-Setup`. Diag : `python -m device.accel`. Sur le globe WORLD3, l'axe Y du capteur decale le point de vue (yaw) sans inertie ni arret de la rotation de repos ; le doigt ne tourne qu'a l'horizontal.

`-Setup` ajoute aussi un minuteur, `sp2050-sync.timer`, qui reprend les futurs au demarrage et toutes les six heures des que le reseau est la. Le dossier `var/sp2050/` du Pi n'est pas ecrase par un deploiement.

## Jouer

- 2026 : le globe, l'annee, les chiffres, trois petits boutons (reglages, courbes, pause).
- Le grand bouton nomme le prochain conseil, par exemple `2030 - PROCHAIN CONSEIL >`.
- Les annees et les chiffres defilent. La terre tourne. Un evenement peut s'arreter au passage. `CONTINUER`, comme le choix d'un dilemme, ramene a la planete et au bouton du conseil suivant.
- Au conseil : trois jetons pour les orientations, puis un dilemme. Le bouton i ouvre la fiche.
- Pause : la terre tourne, on peut la faire glisser, l'annee, et `PLAY`.
- Echap ferme une fiche, ou quitte le jeu depuis le globe.

Editeur des cartes, a part :

```bash
python -m world3.editor
```

Il ecrit `contenu.json`. Relancer le jeu pour lire les textes.

La partie est dans `save.json`, a cote de `main.py`.

## Credits

Les chiffres viennent de World3, pas d'une regle de jeu inventee. Les equations sont celles de 1972. Le recit des scenarios reprend aussi les livres de 1992 et de 2004. Donella H. Meadows, Dennis L. Meadows, Jorgen Randers, William W. Behrens, *The Limits to Growth*, 1972. Dennis L. Meadows et al., *Dynamics of Growth in a Finite World*, 1974.

Moteur : [PyWorld3](https://github.com/cvanwynsberghe/pyworld3), Charles Vanwynsberghe, licence CeCILL 2.1. Le code de ce jeu est a part ; il appelle la bibliotheque, il ne la recopie pas.

Sons : le jeu les calcule. Clics secs, courts, legers.

La planete est un dessin. Ses couleurs suivent la nourriture, la pollution, la population et les ressources restantes. Les calottes sont une carte, pas une temperature : World3 ne calcule pas le climat.
