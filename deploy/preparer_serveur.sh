#!/usr/bin/env bash
# Prépare une instance Ubuntu 24.04 neuve pour le site. À lancer une seule fois,
# en root, sur le serveur, depuis le Mac :
#
#     scp -r deploy root@<adresse>:/root/
#     ssh root@<adresse> bash /root/deploy/preparer_serveur.sh meteo2100.fr
#
# Ce que fait le script, dans l'ordre (docs/deploiement.md, étape 3) :
#   1. mises à jour du système, et leur installation automatique par la suite ;
#   2. nginx, certbot, rsync, pare-feu (ssh, http et https seulement) ;
#   3. un utilisateur « meteo » sans mot de passe, qui reçoit la clé ssh de root,
#      et qui ne peut que relancer le site (sudoers) ;
#   4. Python 3.14 (uv) et son environnement dans /srv/meteo2100/venv ;
#   5. le service systemd et la configuration nginx, journal gardé 14 jours.
# Il ne touche ni au disque des données (à monter avant, docs/deploiement.md)
# ni au HTTPS (certbot, une fois que le domaine pointe sur la machine).
# Le relancer ne casse rien : chaque étape vérifie ce qui est déjà fait.

set -euo pipefail

DOMAINE="${1:?usage : preparer_serveur.sh DOMAINE (ex. meteo2100.fr)}"
ICI="$(cd "$(dirname "$0")" && pwd)"
RACINE=/srv/meteo2100
PYTHON=3.14

[ "$(id -u)" -eq 0 ] || { echo "À lancer en root (sudo)." >&2; exit 1; }
mountpoint -q "$RACINE/data" || {
  echo "$RACINE/data n'est pas un disque monté : monter d'abord le volume des données." >&2
  exit 1
}

echo "== 1. Système"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -yq
apt-get install -yq nginx certbot python3-certbot-nginx rsync ufw unattended-upgrades curl
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== 2. Pare-feu"
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

echo "== 3. Utilisateur meteo"
id meteo >/dev/null 2>&1 || adduser --disabled-password --gecos "" meteo
install -d -m 700 -o meteo -g meteo /home/meteo/.ssh
install -m 600 -o meteo -g meteo /root/.ssh/authorized_keys /home/meteo/.ssh/authorized_keys
cat > /etc/sudoers.d/meteo2100 <<'EOF'
meteo ALL=(root) NOPASSWD: /usr/bin/systemctl restart meteo2100, /usr/bin/systemctl status meteo2100
EOF
chmod 440 /etc/sudoers.d/meteo2100
visudo -cf /etc/sudoers.d/meteo2100
# Connexion par clé seulement.
cat > /etc/ssh/sshd_config.d/10-meteo2100.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
systemctl reload ssh
install -d -o meteo -g meteo "$RACINE" "$RACINE/app" "$RACINE/data"

echo "== 4. Python $PYTHON"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
# Python hors de /home : le service n'a pas accès aux dossiers personnels.
install -d -o meteo -g meteo "$RACINE/python"
[ -x "$RACINE/venv/bin/python" ] || \
  sudo -u meteo env UV_PYTHON_INSTALL_DIR="$RACINE/python" uv venv --python "$PYTHON" "$RACINE/venv"

echo "== 5. Service et nginx"
install -m 644 "$ICI/meteo2100.service" /etc/systemd/system/meteo2100.service
systemctl daemon-reload
systemctl enable meteo2100
install -m 644 "$ICI/nginx_proxy.conf" /etc/nginx/snippets/meteo2100_proxy.conf
sed "s/DOMAINE/$DOMAINE/g" "$ICI/nginx.conf" > /etc/nginx/sites-available/meteo2100
ln -sf /etc/nginx/sites-available/meteo2100 /etc/nginx/sites-enabled/meteo2100
rm -f /etc/nginx/sites-enabled/default
# Journal des visites : un fichier par jour, 14 jours (mentions légales).
sed -i -E 's/^(\s*)rotate [0-9]+/\1rotate 14/; s/^(\s*)(weekly|monthly)/\1daily/' /etc/logrotate.d/nginx
nginx -t
systemctl reload nginx

echo
echo "Prêt. Ensuite, depuis le Mac : deploy/envoyer.sh meteo@<adresse> tout"
echo "puis, une fois le domaine pointé ici : certbot --nginx -d $DOMAINE -d www.$DOMAINE"
