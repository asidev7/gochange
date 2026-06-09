#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# GoChange — installation initiale sur un VPS Ubuntu/Debian.
# À lancer UNE FOIS, en root (ou avec sudo) :  sudo bash deploy/bootstrap.sh
# ----------------------------------------------------------------------------
set -euo pipefail

APP_DIR=/var/www/gochange
REPO=https://github.com/asidev7/gochange.git
DOMAIN=gochange.store

echo ">> Paquets système"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git nginx \
    certbot python3-certbot-nginx postgresql postgresql-contrib

echo ">> Base PostgreSQL (gochange)"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='gochange'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE gochange;"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='gochange'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER gochange WITH PASSWORD 'CHANGE_ME_DB';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE gochange TO gochange;"

echo ">> Récupération du code dans $APP_DIR"
mkdir -p "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo ">> Environnement Python"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo ">> Fichier .env"
if [ ! -f "$APP_DIR/.env" ]; then
  cp deploy/.env.production.example .env
  echo "   !! Éditez $APP_DIR/.env (SECRET_KEY, DATABASE_URL, clés paiement, SMTP) puis relancez deploy.sh"
fi

echo ">> Migrations, seed, statiques"
set -a; source .env; set +a
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py seed
./venv/bin/python manage.py collectstatic --noinput

echo ">> Permissions"
chown -R www-data:www-data "$APP_DIR"

echo ">> Service Gunicorn (systemd)"
cp deploy/gunicorn.service /etc/systemd/system/gochange.service
systemctl daemon-reload
systemctl enable --now gochange

echo ">> Nginx"
cp deploy/nginx-gochange.conf /etc/nginx/sites-available/gochange
ln -sf /etc/nginx/sites-available/gochange /etc/nginx/sites-enabled/gochange
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ">> HTTPS (Let's Encrypt)"
echo "   Lancez :  certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "Terminé. Vérifiez le DNS de $DOMAIN -> IP du VPS avant certbot."
