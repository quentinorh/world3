#!/bin/bash
# Installation de WORLD3 sur un Raspberry Pi 3 Model B+.
# A lancer sur le Pi, avec l'utilisateur habituel (il appelle sudo) :
#   bash ~/world3/deploy/setup-pi.sh
# Depuis Windows, deploy\deploy.ps1 -Setup s'en charge.

set -euo pipefail
# Une coupure SSH envoie SIGHUP. Le script doit finir quand meme.
trap '' HUP
# ssh n'a pas /usr/sbin : reboot et visudo y sont, et set -e quitte sans rien dire.
export PATH="/usr/local/sbin:/usr/sbin:/sbin:${PATH}"

if [ "$(id -u)" -eq 0 ]; then
  echo "Lancez ce script avec l'utilisateur du Pi, pas avec root." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
BEGIN="# --- WORLD3 / Waveshare 4inch HDMI LCD (C) ---"
END="# --- fin WORLD3 ---"
DTBO_URL="https://files.waveshare.com/wiki/4inch%20HDMI%20LCD%20(C)/4HDMIB_DTBO.zip"

stage=""
cleanup() {
  if [ -n "${stage}" ]; then
    rm -rf "${stage}"
  fi
}
trap cleanup EXIT

echo "WORLD3 : preparation du Pi pour ${USER_NAME} (${ROOT})"

if [ -d /boot/firmware/overlays ] && [ -f /boot/firmware/config.txt ]; then
  BOOT=/boot/firmware
elif [ -d /boot/overlays ] && [ -f /boot/config.txt ]; then
  BOOT=/boot
else
  echo "Partition d'amorcage introuvable (/boot/firmware ou /boot)." >&2
  exit 1
fi

model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
echo "Carte : ${model:-inconnue}"
case "${model}" in
  *"Raspberry Pi 5"*) overlay="waveshare-4dpic-5b" ;;
  *"Raspberry Pi 4"*) overlay="waveshare-4dpic-4b" ;;
  *) overlay="waveshare-4dpic-3b" ;;
esac
echo "Overlay tactile : ${overlay}"

echo "Paquets (numpy, scipy et pygame viennent du systeme, sans compilation)."
export DEBIAN_FRONTEND=noninteractive
# Le redirecteur de miroirs coupe les gros paquets (scipy) et apt rebacle
# alors la meme file en boucle. Pas de pipeline HTTP, et plusieurs essais.
sudo tee /etc/apt/apt.conf.d/80world3 >/dev/null <<'EOF'
Acquire::Retries "3";
Acquire::http::Timeout "60";
Acquire::https::Timeout "60";
Acquire::http::Pipeline-Depth "0";
Acquire::https::Pipeline-Depth "0";
EOF

install_apt() {
  local attempt
  for attempt in 1 2 3 4; do
    echo "Telechargement des paquets, essai ${attempt}/4."
    sudo rm -rf /var/cache/apt/archives/partial
    if sudo apt-get update && sudo apt-get install -y --no-install-recommends "$@"; then
      return 0
    fi
    echo "Le miroir a interrompu le telechargement."
    sleep $((attempt * 8))
  done
  return 1
}

use_direct_mirror() {
  local uri="$1"
  local f
  echo "Miroir direct : ${uri}"
  for f in /etc/apt/sources.list /etc/apt/sources.list.d/*; do
    [ -f "${f}" ] || continue
    grep -q 'raspbian' "${f}" || continue
    if [ ! -f "${f}.world3-bak" ]; then
      sudo cp -a "${f}" "${f}.world3-bak"
    fi
    sudo sed -i -E "s#https?://[^[:space:]]*raspbian[^[:space:]]*#${uri}#g" "${f}"
  done
}

packages=(
  python3
  python3-venv
  python3-pip
  python3-numpy
  python3-scipy
  python3-matplotlib
  python3-pygame
  libegl1
  libgles2
  libgl1-mesa-dri
  unzip
  curl
  ca-certificates
  avahi-daemon
  alsa-utils
  i2c-tools
)

if ! install_apt "${packages[@]}"; then
  switched=0
  for mirror in \
    "http://ftp.halifax.rwth-aachen.de/raspbian/raspbian/" \
    "http://mirror.ox.ac.uk/sites/archive.raspbian.org/archive/raspbian/"
  do
    use_direct_mirror "${mirror}"
    switched=1
    if install_apt "${packages[@]}"; then
      switched=0
      break
    fi
  done
  if [ "${switched}" -ne 0 ]; then
    echo "Impossible de telecharger les paquets. Relancez deploy.ps1 -Setup." >&2
    exit 1
  fi
fi

if [ ! -x "${ROOT}/.venv/bin/python" ]; then
  python3 -m venv --system-site-packages "${ROOT}/.venv"
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_CACHE_DIR=1
"${ROOT}/.venv/bin/python" -m pip install --upgrade pip
"${ROOT}/.venv/bin/python" -m pip install --upgrade-strategy only-if-needed "pyworld3==1.1"

if ! "${ROOT}/.venv/bin/python" -c 'import pygame; parts = pygame.version.ver.split("."); raise SystemExit(0 if (int(parts[0]), int(parts[1])) >= (2, 5) else 1)'; then
  echo "Le pygame du systeme est anterieur a 2.5. Installation d'une roue."
  "${ROOT}/.venv/bin/python" -m pip install "pygame>=2.5"
fi

echo "Verification des imports. La premiere fois, scipy est long."
MPLBACKEND=Agg "${ROOT}/.venv/bin/python" -c "import numpy, scipy, matplotlib, pygame, pyworld3; print('pygame', pygame.version.ver)"

echo "Fichiers tactile Waveshare."
stage="$(mktemp -d)"
curl -fL --retry 3 --retry-delay 2 -o "${stage}/dtbo.zip" "${DTBO_URL}"
unzip -q -o "${stage}/dtbo.zip" -d "${stage}"
mapfile -t dtbos < <(find "${stage}" -type f -name "waveshare-4dpic-*.dtbo" | sort)
if [ "${#dtbos[@]}" -eq 0 ]; then
  echo "Aucune overlay dans l'archive Waveshare." >&2
  exit 1
fi
sudo cp "${dtbos[@]}" "${BOOT}/overlays/"
if [ ! -f "${BOOT}/overlays/${overlay}.dtbo" ]; then
  echo "Overlay absente : ${BOOT}/overlays/${overlay}.dtbo" >&2
  exit 1
fi

reboot_needed=0
stripped="$(mktemp)"
awk -v b="${BEGIN}" -v e="${END}" '
  $0 == b { skip = 1; next }
  $0 == e { skip = 0; next }
  !skip { print }
' "${BOOT}/config.txt" > "${stripped}"

block="${BEGIN}
# Dalle 720x720. Interrupteur au dos sur I2C, pas sur USB.
dtparam=i2c_arm=on
dtoverlay=${overlay}
hdmi_force_hotplug=1
hdmi_force_mode=1
hdmi_ignore_edid=0xa5000080
config_hdmi_boost=10
hdmi_group=2
hdmi_mode=87
hdmi_timings=720 0 100 20 100 720 0 20 8 20 0 0 0 60 0 48000000 6
hdmi_drive=2
disable_overscan=1
disable_splash=1
start_x=0
gpu_mem=128"

if ! grep -qE '^[[:space:]]*dtoverlay=vc4-kms-v3d([[:space:]]|$)' "${stripped}"; then
  block="${block}
dtoverlay=vc4-kms-v3d"
fi
if ! grep -qE '^[[:space:]]*dtoverlay=disable-bt([[:space:]]|$)' "${stripped}"; then
  block="${block}
dtoverlay=disable-bt"
fi
block="${block}
${END}"

{
  cat "${stripped}"
  printf '\n%s\n' "${block}"
} > "${stripped}.new"

if ! cmp -s "${BOOT}/config.txt" "${stripped}.new"; then
  sudo cp "${stripped}.new" "${BOOT}/config.txt"
  reboot_needed=1
  echo "config.txt mis a jour."
else
  echo "config.txt deja en place."
fi
rm -f "${stripped}" "${stripped}.new"

cmd_file="${BOOT}/cmdline.txt"
cmd="$(tr -d '\n' < "${cmd_file}")"
cmd_orig="${cmd}"
for token in consoleblank=0 vt.global_cursor_default=0; do
  case " ${cmd} " in
    *" ${token} "*) ;;
    *) cmd="${cmd} ${token}" ;;
  esac
done
if [ "${cmd}" != "${cmd_orig}" ]; then
  printf '%s\n' "${cmd}" | sudo tee "${cmd_file}" >/dev/null
  reboot_needed=1
  echo "cmdline.txt mis a jour."
fi

echo "Audio HDMI (prise jack de la dalle) et Wi-Fi sans mise en veille."
card="$(aplay -l 2>/dev/null | awk '
  /^card / {
    id = $3
    gsub(":", "", id)
    if (tolower($0) ~ /hdmi/) { print id; exit }
  }
')"
if [ -n "${card}" ]; then
  sudo tee /etc/asound.conf >/dev/null <<EOF
pcm.!default {
    type plug
    slave.pcm "hw:${card},0"
}
ctl.!default {
    type hw
    card ${card}
}
EOF
  echo "Carte audio : ${card}"
else
  echo "Pas de carte HDMI vue pour l'instant. Le jeu demarre sans son si besoin."
fi

sudo tee /etc/NetworkManager/conf.d/world3-wifi.conf >/dev/null <<'EOF'
[connection]
wifi.powersave = 2
EOF

sudo mkdir -p /etc/ssh/sshd_config.d
sudo tee /etc/ssh/sshd_config.d/world3.conf >/dev/null <<'EOF'
ClientAliveInterval 30
ClientAliveCountMax 6
EOF

groups_add=""
for group_name in video input render audio tty i2c gpio adm systemd-journal; do
  if getent group "${group_name}" >/dev/null; then
    groups_add="${groups_add},${group_name}"
  fi
done
groups_add="${groups_add#,}"
if [ -n "${groups_add}" ]; then
  sudo usermod -aG "${groups_add}" "${USER_NAME}"
fi

# Acces userspace au bus (BMA220). Le tactile Goodix a son propre pilote ;
# sans i2c-dev, /dev/i2c-1 n'existe pas et le Python ne peut pas lire le capteur.
sudo tee /etc/modules-load.d/world3-i2c.conf >/dev/null <<'EOF'
i2c-dev
EOF
sudo modprobe i2c-dev || true

unit_groups=""
for group_name in video input render audio tty i2c; do
  if getent group "${group_name}" >/dev/null; then
    if [ -n "${unit_groups}" ]; then
      unit_groups="${unit_groups} ${group_name}"
    else
      unit_groups="${group_name}"
    fi
  fi
done

sudo tee /etc/systemd/system/world3.service >/dev/null <<EOF
[Unit]
Description=WORLD3
After=systemd-user-sessions.service
Conflicts=getty@tty1.service
ConditionPathExists=${ROOT}/.venv/bin/python

[Service]
Type=simple
User=${USER_NAME}
SupplementaryGroups=${unit_groups}
WorkingDirectory=${ROOT}
Environment=HOME=${HOME_DIR}
# dummy : device/panel.py balaye la dalle. kmsdrm la laisse noire.
Environment=SDL_VIDEODRIVER=dummy
Environment=SDL_AUDIODRIVER=alsa
Environment=PYGAME_HIDE_SUPPORT_PROMPT=1
Environment=MPLBACKEND=Agg
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sh -c 'i=0; while [ ! -e /dev/dri/card0 ]; do i=\$((i+1)); [ "\$i" -ge 20 ] && exit 1; sleep 1; done'
ExecStart=${ROOT}/.venv/bin/python ${ROOT}/main.py --fullscreen
Restart=on-failure
RestartSec=3
StartLimitIntervalSec=90
StartLimitBurst=5
OOMScoreAdjust=200
StandardInput=tty
StandardOutput=journal
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl_bin="$(command -v systemctl)"
reboot_bin="$(command -v reboot)"
poweroff_bin="$(command -v poweroff || true)"
rules="${systemctl_bin} restart world3, ${systemctl_bin} start world3, ${systemctl_bin} stop world3, ${systemctl_bin} status world3, ${reboot_bin}"
if [ -n "${poweroff_bin}" ]; then
  rules="${rules}, ${poweroff_bin}"
fi
sudoers_tmp="$(mktemp)"
cat > "${sudoers_tmp}" <<EOF
${USER_NAME} ALL=(root) NOPASSWD: ${rules}
EOF
sudo visudo -cf "${sudoers_tmp}"
sudo cp "${sudoers_tmp}" /etc/sudoers.d/world3
sudo chmod 440 /etc/sudoers.d/world3
rm -f "${sudoers_tmp}"

sudo tee /etc/systemd/system/sp2050-sync.service >/dev/null <<EOF
[Unit]
Description=Synchronisation des futurs SP2050
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${USER_NAME}
WorkingDirectory=${ROOT}
ExecStart=${ROOT}/.venv/bin/python -m sp2050.sync
EOF

sudo tee /etc/systemd/system/sp2050-sync.timer >/dev/null <<EOF
[Unit]
Description=Synchro SP2050

[Timer]
OnBootSec=45
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable world3.service
sudo systemctl enable sp2050-sync.timer
sudo systemctl start sp2050-sync.timer || true
sudo systemctl disable getty@tty1.service
if systemctl list-unit-files bluetooth.service >/dev/null 2>&1; then
  sudo systemctl disable bluetooth.service || true
fi

flag="${HOME_DIR}/.world3-reboot-required"
if [ "${reboot_needed}" -eq 1 ]; then
  touch "${flag}"
  echo "WORLD3_REBOOT=1"
  echo "Un redemarrage est necessaire pour la dalle. deploy.ps1 s'en charge."
else
  rm -f "${flag}"
  echo "WORLD3_REBOOT=0"
  sudo systemctl restart world3.service
  echo "Service world3 relance."
fi

echo "Modes HDMI connus :"
found_mode=0
for mode_file in /sys/class/drm/card*-HDMI-A-*/mode; do
  if [ -f "${mode_file}" ]; then
    found_mode=1
    echo "  ${mode_file} : $(cat "${mode_file}")"
  fi
done
if [ "${found_mode}" -eq 0 ]; then
  echo "  (aucun pour l'instant, normal avant le redemarrage de la dalle)"
fi

sudo sync
echo "Installation terminee."
sudo sshd -t && sudo systemctl reload ssh || true
