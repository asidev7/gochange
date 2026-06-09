# Déploiement GoChange sur VPS — gochange.store

Cible : VPS **Ubuntu/Debian**, Django + Gunicorn + Nginx + PostgreSQL + HTTPS (Let's Encrypt).

## 0. Pré-requis
- Un VPS avec accès SSH root/sudo.
- Le **DNS de `gochange.store`** (et `www`) pointant vers l'**IP du VPS** :
  - `A    gochange.store      -> IP_DU_VPS`
  - `A    www.gochange.store  -> IP_DU_VPS`
- Vérifier : `dig +short gochange.store` doit renvoyer l'IP du VPS.

## 1. Installation initiale (une seule fois)
Connecté au VPS :
```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/asidev7/gochange.git /var/www/gochange
cd /var/www/gochange
sudo bash deploy/bootstrap.sh
```
Le script installe Python/Nginx/PostgreSQL/Certbot, crée la base, le venv,
applique les migrations, le seed, collecte les statiques, installe le service
Gunicorn et la config Nginx.

## 2. Configurer les secrets
Éditer le `.env` créé puis appliquer :
```bash
sudo nano /var/www/gochange/.env      # SECRET_KEY, DATABASE_URL, clés PayDunya/Paystack LIVE, SMTP
# (mot de passe DB : adaptez aussi CREATE USER ... PASSWORD dans bootstrap si modifié)
cd /var/www/gochange && sudo bash deploy/deploy.sh
```

## 3. Activer HTTPS
```bash
sudo certbot --nginx -d gochange.store -d www.gochange.store
```
Certbot ajoute le bloc 443 et le renouvellement auto. Le site répond alors sur
**https://gochange.store**.

## 4. Webhooks paiement (après HTTPS)
Déclarer ces URLs dans les tableaux de bord des fournisseurs :
- PayDunya (IPN) : `https://gochange.store/webhooks/paydunya/`
- Paystack       : `https://gochange.store/webhooks/paystack/`

## 5. Mises à jour suivantes
À chaque nouveau commit poussé sur `main` :
```bash
cd /var/www/gochange && sudo bash deploy/deploy.sh
```

## Dépannage
- Logs app   : `sudo journalctl -u gochange -f`
- Logs nginx : `sudo tail -f /var/log/nginx/error.log`
- Tester nginx : `sudo nginx -t`
- Redémarrer : `sudo systemctl restart gochange && sudo systemctl reload nginx`

## Notes sécurité
- `DEBUG=False` en prod (déjà géré par `.env`) active HSTS, cookies sécurisés, redirection HTTPS.
- Sauvegarder régulièrement la base : `pg_dump gochange > backup.sql`.
- Changer le mot de passe admin après le premier `seed`.
- Ne jamais committer le `.env` rempli.
