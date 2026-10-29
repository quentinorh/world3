# Copier ce fichier vers deploy\target.ps1 puis adapter.
# target.ps1 reste sur cette machine : il n'est pas envoye au Pi.

$World3Host = "world3.local"
$World3User = "pi"
$World3Port = 22

# Laisser vide pour utiliser la cle par defaut de ssh (~/.ssh/id_ed25519).
$World3Identity = ""
