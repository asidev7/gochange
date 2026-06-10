#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# GoChange — mise à jour (déploiement continu).
# À lancer sur le VPS depuis /var/www/gochange :  bash deploy/deploy.sh
# ----------------------------------------------------------------------------
set -euo pipefail

APP_DIR=/var/www/gochange
cd "$APP_DIR"

echo ">> git pull"
git pull origin main

echo ">> dépendances"
./venv/bin/pip install -r requirements.txt

echo ">> migrations + statiques"
# Pas de `source .env` : settings.py charge le .env via python-dotenv.
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput

echo ">> redémarrage Gunicorn"
sudo systemctl restart gochange

echo "Déploiement terminé : https://gochange.store"
