# GoChange — gochange.store

Plateforme web d'échange de devises **Naira (NGN) ⇄ FCFA (XOF)** pour le corridor
**Bénin–Nigeria**. Dépôts, échanges au taux du jour, retraits Mobile Money / banque,
vérification d'identité (KYC) à 3 niveaux, espace client et administration.

Édité par **ASITECH SOLUTION**, Parakou (Bénin).

> Stack : **Django 6** · PostgreSQL ou SQLite · **Tailwind CDN** + **Alpine.js** ·
> paiements **PayDunya** (XOF) et **Paystack** (NGN).

---

## 1. Démarrage rapide (développement)

```bash
# 1. Dépendances
pip install -r requirements.txt

# 2. Configuration
cp .env.example .env          # SQLite + mode simulation par défaut, rien à modifier

# 3. Base de données
python manage.py migrate

# 4. Données de départ (taux, limites KYC, compte admin)
python manage.py seed

# 5. Lancer
python manage.py runserver
```

Ouvrez **http://127.0.0.1:8000/**.

- Compte admin par défaut : `admin@gochange.store` / `ChangeMoi123!`
  (personnalisable via `ADMIN_EMAIL` / `ADMIN_PASSWORD` avant le `seed`).
- En développement, les e-mails (vérification, réinitialisation, décisions KYC)
  s'affichent **dans la console** du serveur.

---

## 2. Mode simulation des paiements

Si `PAYDUNYA_MASTER_KEY` **ou** `PAYSTACK_SECRET_KEY` sont absents du `.env`,
l'application bascule automatiquement en **mode simulation** :

- aucun appel réseau réel n'est effectué ;
- un dépôt est **confirmé automatiquement** au retour de paiement (crédit du solde) ;
- `bank/resolve` renvoie un **nom de titulaire fictif** pour démontrer la confirmation
  de bénéficiaire ;
- les décaissements/virements sont simulés comme réussis.

Cela permet de tester l'intégralité des flux **sans clé API**. Pour passer en mode réel,
renseignez vos clés **test** PayDunya et Paystack dans `.env` ; la simulation se désactive seule.

---

## 3. Configuration `.env`

| Variable | Rôle |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django de base |
| `DATABASE_URL` | vide → SQLite ; sinon `postgres://user:pass@host:5432/db` |
| `EMAIL_HOST`, `EMAIL_PORT`, … | SMTP ; vide → console |
| `PAYDUNYA_*` | clés PayDunya (XOF) + `PAYDUNYA_MODE=test\|live` |
| `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` | clés Paystack (NGN) |
| `WHATSAPP_NUMBER`, `CONTACT_EMAIL` | coordonnées affichées sur le site |

### Passer à PostgreSQL

```bash
# .env
DATABASE_URL=postgres://gochange:motdepasse@localhost:5432/gochange
```
puis `python manage.py migrate && python manage.py seed`.

---

## 4. Architecture

```
config/      Paramètres, URLs racine, WSGI/ASGI
accounts/    CustomUser (login e-mail), auth, profil, paramètres, KYC (3 niveaux)
wallet/      Wallet (soldes NGN/XOF), Beneficiary
exchange/    ExchangeRate, Deposit, ExchangeTransaction, Withdrawal, WebhookLog
             services/ : paydunya.py, paystack.py, limits.py
core/        Pages publiques, contact, SEO (robots.txt, sitemap.xml)
templates/   base + composants + pages publiques / compte / espace connecté / e-mails
static/      CSS d'appoint, favicon, image Open Graph
```

### Modèles
`CustomUser`, `Wallet`, `ExchangeRate`, `KYCProfile`, `KYCDocument`, `DailyLimit`,
`Deposit`, `ExchangeTransaction`, `Withdrawal`, `Beneficiary`, `WebhookLog`.
Montants en `DecimalField`, soldes mis à jour sous `select_for_update`, webhooks idempotents
via `WebhookLog`.

---

## 5. KYC — niveaux et limites

| Niveau | Conditions | Dépôt / jour | Retrait / jour |
|---|---|---|---|
| **L1** | e-mail + téléphone (auto à l'inscription) | 50 000 FCFA | 50 000 FCFA |
| **L2** | pièce d'identité + selfie (validation admin) | 500 000 FCFA | 500 000 FCFA |
| **L3** | L2 + justificatif d'adresse / RCCM | 2 000 000 FCFA | 2 000 000 FCFA |

Les limites sont **stockées en base** (modifiables dans l'admin), **vérifiées côté serveur**
avant chaque dépôt/retrait, avec compteur journalier remis à zéro à minuit.
L'utilisateur téléverse ses documents depuis `/profil/kyc/` ; l'admin approuve/rejette
(`Profils KYC` → actions), ce qui déclenche un e-mail automatique.

---

## 6. Flux de paiement

- **Dépôt XOF** → PayDunya `checkout-invoice/create` → redirection → crédit **après IPN** confirmé.
- **Dépôt NGN** → Paystack `transaction/initialize` (kobo) → crédit après `verify` + webhook signé.
- **Échange** → `montant × taux − frais %`, opération **atomique**, **taux figé** à la validation.
- **Retrait XOF** → décaissement PayDunya (Mobile Money).
- **Retrait NGN** → `bank/list` → compte 10 chiffres → **`bank/resolve` (nom du titulaire)**
  → case « Je confirme le bénéficiaire » → `transferrecipient` + `transfer` → statut via webhook.

> La clé secrète Paystack **n'est jamais exposée** au frontend : la résolution de compte
> passe par un endpoint Django proxy (`/api/resoudre-compte/`).

Endpoints webhooks à déclarer chez les fournisseurs :
`/webhooks/paydunya/` et `/webhooks/paystack/`.

---

## 7. Administration

`/admin/` (interface Jazzmin) : taux & frais, utilisateurs, validation des documents KYC,
**approbation + décaissement des retraits** (action dédiée), dépôts/échanges/retraits,
journal des webhooks.

---

## 8. SEO

- `/robots.txt` — autorise les pages publiques, bloque l'espace connecté, `/admin`, `/api`, `/webhooks`.
- `/sitemap.xml` — généré par `django.contrib.sitemaps`.
- Balises **meta + Open Graph** par page, titres uniques, domaine canonique `https://gochange.store`.

---

## 9. Tests

```bash
python manage.py test
```
Couvre l'échange atomique (taux figé, débit/crédit, solde insuffisant), l'idempotence du
crédit de dépôt, l'application des limites journalières et le débit lors d'un retrait.

---

## 10. Mise en production (résumé)

1. `DEBUG=False`, `SECRET_KEY` robuste, `ALLOWED_HOSTS` = `gochange.store`.
2. `DATABASE_URL` PostgreSQL.
3. Clés **live** PayDunya/Paystack + URLs de webhooks publiques (HTTPS).
4. `python manage.py collectstatic` (WhiteNoise sert les fichiers statiques).
5. Servir via `gunicorn config.wsgi` derrière un reverse proxy HTTPS.
6. Configurer le SMTP (`EMAIL_HOST`…) pour l'envoi réel des e-mails.

---

© GoChange — ASITECH SOLUTION, Parakou (Bénin).
