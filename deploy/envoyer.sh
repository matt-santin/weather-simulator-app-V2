#!/usr/bin/env bash
# Envoie le site sur le serveur, depuis le Mac (docs/deploiement.md) :
#
#     deploy/envoyer.sh meteo@<adresse> code      # le code, puis relance
#     deploy/envoyer.sh meteo@<adresse> donnees   # les stockages, puis relance
#     deploy/envoyer.sh meteo@<adresse> tout      # les deux
#
# Le code envoyé est celui du dernier commit, pas les fichiers en cours de
# modification : ce qui tourne en ligne est toujours dans git. Refusé si une
# page contient encore « à compléter » (mentions légales).
#
# Les données vont dans serve.next, à côté de serve : rsync ne transfère que ce
# qui a changé et lie les fichiers identiques à ceux de serve (--link-dest), sans
# les copier. Le site continue de lire serve pendant tout l'envoi ; à la fin,
# serve.next prend sa place et le site est relancé (quelques secondes). Un envoi
# interrompu reprend où il s'était arrêté : relancer la même commande.
# Pas envoyés : les tableaux de pression de point.zarr (era5/psl, cordex/psl),
# que le serveur ne lit jamais (les isobares viennent de map.zarr).

set -euo pipefail

HOTE="${1:?usage : envoyer.sh meteo@<adresse> code|donnees|tout}"
QUOI="${2:?usage : envoyer.sh meteo@<adresse> code|donnees|tout}"
DEPOT="$(cd "$(dirname "$0")/.." && pwd)"
RACINE=/srv/meteo2100
SERVE="$DEPOT/data/serve"

relancer() {
  ssh "$HOTE" "sudo systemctl restart meteo2100"
  echo "Relancé. Vérification..."
  for _ in $(seq 1 30); do
    if ssh "$HOTE" "curl -sf http://127.0.0.1:8000/api/health" >/dev/null; then
      echo "Le site répond."
      return
    fi
    sleep 2
  done
  echo "Le site ne répond pas : ssh $HOTE sudo systemctl status meteo2100" >&2
  exit 1
}

envoyer_code() {
  cd "$DEPOT"
  if grep -rl "à compléter" web/pages; then
    echo "Pages à compléter avant l'envoi (ci-dessus)." >&2
    exit 1
  fi
  if ! git diff --quiet HEAD -- src web deploy requirements-server.txt; then
    echo "Attention : des modifications de src, web ou deploy ne sont pas dans un commit et ne partiront pas."
  fi
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  git archive HEAD src web deploy requirements-server.txt | tar -x -C "$tmp"
  echo "Code : commit $(git rev-parse --short HEAD)"
  rsync -a --delete "$tmp/" "$HOTE:$RACINE/app/"
  ssh "$HOTE" "VIRTUAL_ENV=$RACINE/venv uv pip install -q -r $RACINE/app/requirements-server.txt"
}

envoyer_donnees() {
  for f in point.zarr map.zarr places.tsv; do
    [ -e "$SERVE/$f" ] || { echo "Manque $SERVE/$f" >&2; exit 1; }
  done
  local lien=()
  if ssh "$HOTE" "test -d $RACINE/data/serve"; then
    lien=(--link-dest="$RACINE/data/serve")
  fi
  echo "Données : envoi vers serve.next (reprise possible)..."
  # caffeinate : le Mac ne se met pas en veille pendant l'envoi.
  caffeinate -i rsync -a --delete --partial ${lien[@]+"${lien[@]}"} \
    --exclude=/point.zarr/era5/psl --exclude=/point.zarr/cordex/psl \
    "$SERVE/point.zarr" "$SERVE/map.zarr" "$SERVE/places.tsv" \
    "$HOTE:$RACINE/data/serve.next/"
  echo "Bascule de serve.next en serve..."
  ssh "$HOTE" "set -e; cd $RACINE/data; rm -rf serve.old; \
    if [ -d serve ]; then mv serve serve.old; fi; mv serve.next serve"
}

case "$QUOI" in
  code) envoyer_code; relancer ;;
  donnees) envoyer_donnees; relancer; ssh "$HOTE" "rm -rf $RACINE/data/serve.old" ;;
  tout) envoyer_code; envoyer_donnees; relancer; ssh "$HOTE" "rm -rf $RACINE/data/serve.old" ;;
  *) echo "code, donnees ou tout" >&2; exit 1 ;;
esac
