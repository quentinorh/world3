<#
.SYNOPSIS
    Envoie WORLD3 sur le Raspberry Pi par SSH et l'y installe.

.DESCRIPTION
    A lancer depuis la racine du projet, ou depuis n'importe ou :
    le dossier du depot est le parent de ce script.

    Premiere fois, apres avoir copie target.example.ps1 vers target.ps1 :

        powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -InstallKey
        powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -Setup

    Les fois suivantes :

        powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1

    -Setup installe les paquets, la dalle Waveshare et le service.
    Sans -Setup, le code est copie, les futurs SP2050 sont synchronises
    si le Pi a Internet, et le menu est relance.
    save.json deja present sur le Pi n'est pas ecrase.
    var/carte/terre.pmtiles est envoye seulement s'il est deja sur
    cet ordinateur et que sa taille differe. Un deploiement ne l'efface pas.

.PARAMETER Setup
    Installe le systeme sur le Pi, puis redemarre si la dalle l'exige.

.PARAMETER InstallKey
    Ajoute la cle publique locale dans authorized_keys. Demande le mot
    de passe SSH une fois. Cree une cle ed25519 si elle n'existe pas.

.PARAMETER Status
    Affiche l'etat du service world3.

.PARAMETER Logs
    Affiche les dernieres lignes du journal du jeu.

.PARAMETER NoRestart
    Copie les fichiers sans relancer la partie.

.PARAMETER TargetHost
    Hote SSH. Remplace target.ps1 pour cet appel.

.PARAMETER User
    Utilisateur SSH. Remplace target.ps1 pour cet appel.
#>
[CmdletBinding()]
param(
    [string]$TargetHost,
    [string]$User,
    [int]$Port = 0,
    [string]$IdentityFile,
    [switch]$Setup,
    [switch]$InstallKey,
    [switch]$Status,
    [switch]$Logs,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$World3Host = "world3.local"
$World3User = "pi"
$World3Port = 22
$World3Identity = ""

$configPath = Join-Path $PSScriptRoot "target.ps1"
if (Test-Path -LiteralPath $configPath) {
    . $configPath
}
if ($PSBoundParameters.ContainsKey("TargetHost") -and $TargetHost) {
    $World3Host = $TargetHost
}
if ($PSBoundParameters.ContainsKey("User") -and $User) {
    $World3User = $User
}
if ($Port -gt 0) {
    $World3Port = $Port
}
if ($PSBoundParameters.ContainsKey("IdentityFile")) {
    $World3Identity = $IdentityFile
}

function Quote-Bash([string]$Text) {
    return "'" + ($Text -replace "'", "'\''") + "'"
}

function Get-Tool([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Commande introuvable : $Name. Installez le client OpenSSH (Parametres Windows, Fonctionnalites facultatives)."
    }
    return $cmd.Source
}

$ssh = Get-Tool "ssh"
$scp = Get-Tool "scp"
$tar = Get-Tool "tar"

$sshOpts = @(
    "-p", "$World3Port",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=120"
)
$scpOpts = @(
    "-P", "$World3Port",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=120"
)
if ($World3Identity) {
    if (-not (Test-Path -LiteralPath $World3Identity)) {
        throw "Cle introuvable : $World3Identity"
    }
    $sshOpts += @("-i", $World3Identity)
    $scpOpts += @("-i", $World3Identity)
}

$Target = "${World3User}@${World3Host}"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-Remote {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [switch]$TTY
    )
    $argList = @()
    if ($TTY) { $argList += "-t" }
    $argList += $sshOpts
    $argList += $Target
    $argList += $Command
    & $ssh @argList
    $script:RemoteExit = $LASTEXITCODE
}

function Copy-MapIfPresent {
    $localMap = Join-Path $Root "var\carte\terre.pmtiles"
    if (-not (Test-Path -LiteralPath $localMap)) {
        Write-Host "Pas de carte sur cet ordinateur. Celle du Pi, s'il y en a une, reste."
        return
    }
    $localSize = (Get-Item -LiteralPath $localMap).Length
    $remoteMap = "$remoteDir/var/carte/terre.pmtiles"
    $quotedMap = Quote-Bash $remoteMap
    $remoteRaw = (& $ssh @sshOpts $Target "if [ -f $quotedMap ]; then stat -c %s $quotedMap; else printf missing; fi")
    if ($LASTEXITCODE -ne 0) {
        throw "Impossible de lire la carte sur le Pi."
    }
    if ("$remoteRaw".Trim() -eq "$localSize") {
        Write-Host "Carte deja sur le Pi ($localSize octets)."
        return
    }
    Write-Host "Envoi de la carte ($localSize octets)..."
    $quotedDir = Quote-Bash "$remoteDir/var/carte"
    Invoke-Remote "mkdir -p $quotedDir"
    if ($script:RemoteExit -ne 0) { throw "Impossible de creer var/carte sur le Pi." }
    & $scp @scpOpts $localMap "${Target}:${remoteMap}"
    if ($LASTEXITCODE -ne 0) { throw "L'envoi de la carte a echoue." }
    Write-Host "Carte en place."
}

Write-Host "Cible : $Target"

if ($InstallKey) {
    $priv = $World3Identity
    if (-not $priv) {
        $priv = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
    }
    $pub = "$priv.pub"
    if (-not (Test-Path -LiteralPath $pub)) {
        $dir = Split-Path -Parent $priv
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir | Out-Null
        }
        Write-Host "Creation de la cle $priv"
        & cmd.exe /c "ssh-keygen -t ed25519 -f `"$priv`" -N `"`" -q"
        if ($LASTEXITCODE -ne 0) { throw "ssh-keygen a echoue." }
    }
    $line = (Get-Content -LiteralPath $pub -Raw).Trim()
    $escaped = $line.Replace("'", "'\''")
    Write-Host "Envoi de la cle. Le mot de passe SSH est demande une fois."
    Invoke-Remote "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; grep -qxF '$escaped' ~/.ssh/authorized_keys || printf '%s\n' '$escaped' >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
    if ($script:RemoteExit -ne 0) { throw "Impossible d'installer la cle." }
    Write-Host "Cle installee."
    if (-not $Setup -and -not $Status -and -not $Logs) {
        return
    }
}

if ($Status) {
    Invoke-Remote "systemctl status world3 --no-pager --lines=20 || true"
    return
}

if ($Logs) {
    Invoke-Remote "journalctl -u world3 -n 120 --no-pager || sudo journalctl -u world3 -n 120 --no-pager" -TTY
    return
}

Write-Host "Connexion..."
$null = & $ssh @sshOpts $Target "printf ok"
if ($LASTEXITCODE -ne 0) {
    throw "SSH vers $Target a echoue. Verifiez le Wi-Fi, le nom et que SSH est actif. -InstallKey envoie une cle si vous avez encore le mot de passe."
}

$remoteHome = (& $ssh @sshOpts $Target 'printf %s "$HOME"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $remoteHome) {
    throw "Impossible de lire le dossier personnel sur le Pi."
}
$remoteDir = "$remoteHome/world3"
Write-Host "Dossier distant : $remoteDir"

$archive = Join-Path $env:TEMP "world3-deploy.tgz"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

Get-ChildItem -LiteralPath $Root -Recurse -Filter *.sh -File | ForEach-Object {
    $text = [IO.File]::ReadAllText($_.FullName)
    $unix = $text -replace "`r`n", "`n" -replace "`r", "`n"
    if ($unix -ne $text) {
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [IO.File]::WriteAllText($_.FullName, $unix, $utf8)
    }
}

Write-Host "Archive du projet..."
& $tar -c -z -f $archive `
    --exclude=.git `
    --exclude=.venv `
    --exclude=__pycache__ `
    --exclude=shots `
    --exclude=save.json `
    --exclude=var `
    --exclude=deploy/target.ps1 `
    -C $Root .
if ($LASTEXITCODE -ne 0) { throw "La creation de l'archive a echoue." }

Write-Host "Transfert..."
& $scp @scpOpts $archive "${Target}:/tmp/world3-deploy.tgz"
if ($LASTEXITCODE -ne 0) { throw "scp a echoue." }
Remove-Item -LiteralPath $archive -Force

$quotedDir = Quote-Bash $remoteDir
Invoke-Remote "mkdir -p $quotedDir && tar -xzf /tmp/world3-deploy.tgz -C $quotedDir && find $quotedDir -name '*.sh' -exec sed -i 's/\r$//' {} + && rm -f /tmp/world3-deploy.tgz"
if ($script:RemoteExit -ne 0) { throw "L'extraction sur le Pi a echoue." }
Write-Host "Fichiers en place. save.json du Pi, s'il existe, est conserve."
Copy-MapIfPresent

if ($Setup) {
    Write-Host "Installation. Le mot de passe sudo du Pi peut etre demande. Comptez plusieurs minutes."
    $quotedSetup = Quote-Bash "$remoteDir/deploy/setup-pi.sh"
    Invoke-Remote "bash $quotedSetup" -TTY
    $setupExit = $script:RemoteExit
    if ($setupExit -ne 0) {
        Write-Host "La liaison SSH a coupe. Attente du Pi : l'installation peut finir sans elle."
        Start-Sleep -Seconds 5
        $back = $false
        for ($i = 0; $i -lt 12; $i++) {
            $null = & $ssh @sshOpts -o ConnectTimeout=5 -o LogLevel=ERROR $Target "printf ok"
            if ($LASTEXITCODE -eq 0) { $back = $true; break }
            Start-Sleep -Seconds 5
        }
        if (-not $back) {
            throw "L'installation sur le Pi a echoue, et le Pi ne repond plus."
        }
    }

    $flag = (& $ssh @sshOpts $Target 'if [ -f "$HOME/.world3-reboot-required" ]; then printf yes; else printf no; fi').Trim()
    if ($setupExit -ne 0 -and $flag -ne "yes") {
        throw "L'installation s'est arretee avant la fin. Relancez deploy.ps1 -Setup."
    }
    if ($flag -eq "yes") {
        Write-Host "Redemarrage pour la dalle 720x720."
        Invoke-Remote "rm -f ~/.world3-reboot-required && sudo reboot" -TTY
        Write-Host "Attente du retour du Pi..."
        Start-Sleep -Seconds 12
        $up = $false
        for ($i = 0; $i -lt 36; $i++) {
            $null = & $ssh @sshOpts -o ConnectTimeout=5 -o LogLevel=ERROR $Target "printf ok"
            if ($LASTEXITCODE -eq 0) {
                $up = $true
                break
            }
            Start-Sleep -Seconds 5
        }
        if (-not $up) {
            throw "Le Pi ne repond pas encore. Quand il est de retour : deploy\deploy.ps1 -Status"
        }
        Write-Host "Le Pi a redemarre. Le menu doit occuper l'ecran."
        return
    }
    Write-Host "Le menu tourne. Journal : deploy\deploy.ps1 -Logs"
    return
}

Write-Host "Synchro des futurs, si le Pi a Internet."
$quotedPy = Quote-Bash "$remoteDir/.venv/bin/python"
Invoke-Remote "cd $quotedDir && if [ -x $quotedPy ]; then $quotedPy -m sp2050.sync || true; fi"

if ($NoRestart) {
    Write-Host "Copie terminee, sans relance."
    return
}

Write-Host "Relance du menu..."
Invoke-Remote "sudo systemctl restart world3" -TTY
if ($script:RemoteExit -ne 0) {
    throw "Le service world3 n'a pas redemarre. La premiere fois, utilisez -Setup."
}
Write-Host "Le menu tourne. Journal : deploy\deploy.ps1 -Logs"
