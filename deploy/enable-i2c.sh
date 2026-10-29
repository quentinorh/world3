#!/bin/bash
# Active /dev/i2c-1 (i2c-dev) et le groupe i2c pour world3.service.
# Sur le Pi : bash ~/world3/deploy/enable-i2c.sh
# Depuis Windows : ssh -t pi@IP 'bash ~/world3/deploy/enable-i2c.sh'

set -euo pipefail
export PATH="/usr/local/sbin:/usr/sbin:/sbin:${PATH}"

if [ "$(id -u)" -eq 0 ]; then
  echo "Lancez avec l'utilisateur pi, pas root." >&2
  exit 1
fi

echo "Chargement de i2c-dev..."
sudo tee /etc/modules-load.d/world3-i2c.conf >/dev/null <<'EOF'
i2c-dev
EOF
sudo modprobe i2c-dev

if [ ! -e /dev/i2c-1 ]; then
  echo "Toujours pas de /dev/i2c-1 apres modprobe." >&2
  ls -l /dev/i2c-* 2>&1 || true
  exit 1
fi
echo "OK : $(ls -l /dev/i2c-1)"

unit=/etc/systemd/system/world3.service
if [ -f "${unit}" ]; then
  if grep -q '^SupplementaryGroups=.*\bi2c\b' "${unit}"; then
    echo "world3.service a deja le groupe i2c."
  else
    echo "Ajout du groupe i2c a world3.service..."
    tmp="$(mktemp)"
    if grep -q '^SupplementaryGroups=' "${unit}"; then
      sed -E 's/^(SupplementaryGroups=.*)$/\1 i2c/' "${unit}" > "${tmp}"
    else
      sed '/^User=/a SupplementaryGroups=i2c' "${unit}" > "${tmp}"
    fi
    sudo cp "${tmp}" "${unit}"
    rm -f "${tmp}"
    sudo systemctl daemon-reload
  fi
fi

if command -v i2cdetect >/dev/null; then
  echo "Scan I2C1 (BMA220 = 0x0a ou 0x0b) :"
  sudo i2cdetect -y 1 || i2cdetect -y 1 || true
else
  echo "i2c-tools absent : apt install i2c-tools pour i2cdetect."
fi

echo "Relance du menu..."
sudo systemctl restart world3
echo "Fait. Ouvrez le bouton g du menu pour retester."
