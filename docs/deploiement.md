# Déploiement

Le site en ligne : une instance Scaleway (Paris), Ubuntu 24.04, les stockages sur un volume Block attaché. nginx reçoit les visiteurs (HTTPS, limites par adresse IP) et transmet à uvicorn, qui lit les stockages. Choix du 25/11/2026 : Scaleway, données sur disque ; l'Object Storage est gardé pour le passage au monde.

| Fichier | Rôle |
|---|---|
| `deploy/preparer_serveur.sh` | prépare une instance neuve, une seule fois (système, pare-feu, utilisateur `meteo`, Python 3.14, service, nginx) |
| `deploy/meteo2100.service` | service systemd : uvicorn, 2 processus, relancé s'il s'arrête |
| `deploy/nginx.conf`, `deploy/nginx_proxy.conf` | nginx devant uvicorn, limites de requêtes |
| `deploy/envoyer.sh` | envoie le code (dernier commit) et les données depuis le Mac, puis relance |
| `web/pages/legal.html` | mentions légales, `/mentions-legales` |

## Sur le serveur

```
/srv/meteo2100/app       code (src, web, deploy, requirements-server.txt)
/srv/meteo2100/venv      Python 3.14 et dépendances
/srv/meteo2100/python    Python installé par uv
/srv/meteo2100/data      volume Block monté ; WSA_DATA pointe ici
    serve/                 point.zarr, map.zarr, places.tsv : ce que lit le site
    serve.next/            envoi en cours (deploy/envoyer.sh donnees)
```

Envoyés : `point.zarr` sans `era5/psl` ni `cordex/psl` (jamais lus), `map.zarr`, `places.tsv`, soit environ 79 Go.

## Étapes, la première fois

1. **Console Scaleway** (à faire par le propriétaire du compte) :
   - clé ssh du Mac (`~/.ssh/id_ed25519.pub`) dans Projet, Clés SSH ;
   - instance DEV1-S, Paris, Ubuntu 24.04, IPv4 flexible ;
   - volume Block de 100 Go attaché à l'instance (79 Go de données, et de la place pour les fichiers changés d'une mise à jour) ;
   - alerte de consommation sur le compte.
2. **Monter le volume** (en root sur le serveur ; `mkfs` efface le disque désigné : vérifier avec `lsblk` que c'est bien le volume vide de 100 Go) :
   ```
   lsblk
   mkfs.ext4 -L donnees /dev/sdX
   mkdir -p /srv/meteo2100/data
   echo 'LABEL=donnees /srv/meteo2100/data ext4 defaults,nofail 0 2' >> /etc/fstab
   mount -a && df -h /srv/meteo2100/data
   ```
3. **Préparer le serveur**, depuis le Mac :
   ```
   scp -r deploy root@<adresse>:/root/
   ssh root@<adresse> bash /root/deploy/preparer_serveur.sh meteo2100.fr
   ```
4. **Envoyer le site**, depuis le Mac (les données prennent plusieurs heures ; une coupure se rattrape en relançant) :
   ```
   deploy/envoyer.sh meteo@<adresse> tout
   ```
   Le site est alors visible à `http://<adresse>`.
5. **Domaine** : chez le registrar, enregistrements A de `meteo2100.fr` et `www.meteo2100.fr` vers l'adresse IPv4. Une fois pris en compte (`dig +short meteo2100.fr`) :
   ```
   ssh root@<adresse> certbot --nginx -d meteo2100.fr -d www.meteo2100.fr
   ```
   certbot ajoute le HTTPS à nginx et le renouvelle seul.

## Mises à jour

- Code : commit, puis `deploy/envoyer.sh meteo@<adresse> code`.
- Données : reconstruire `data/serve` sur le Mac, puis `deploy/envoyer.sh meteo@<adresse> donnees`. Seuls les fichiers changés passent ; le site sert l'ancienne version jusqu'à la bascule. Une reconstruction complète change tous les fichiers et demande deux fois la place : agrandir le volume avant, ou supprimer `serve` (site arrêté pendant l'envoi).

## Arrêter

- Le site seulement : `ssh root@<adresse> systemctl stop meteo2100` (`start` pour le relancer).
- Tout : supprimer l'instance, le volume et l'IP dans la console Scaleway. Une instance éteinte n'est plus facturée pour le calcul, mais le volume et l'IP le restent. Rien n'est perdu : le code est sur GitHub, les données sur le Mac et le LaCie.

## Limites et journal

- nginx : API 10 appels par seconde et par adresse IP (rafale de 40), cartes 2 par seconde (rafale de 12), 20 connexions à la fois ; au-delà, réponse 429.
- Journal des visites : celui de nginx (`/var/log/nginx/access.log`), un fichier par jour, 14 jours, comme le disent les mentions légales. uvicorn n'en écrit pas.
- Journal du site : `journalctl -u meteo2100`.
