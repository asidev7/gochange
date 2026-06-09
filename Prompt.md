# PROMPT GOCHANGE v2 — gochange.store
## Plateforme d'échange Naira ⇄ FCFA (Django)

Construis l'application web complète **GoChange** (domaine : **gochange.store**) : échange de devises NGN ⇄ XOF pour le corridor Bénin–Nigeria.

**Stack** : Django 5 + PostgreSQL + Tailwind CDN + Alpine.js. Paiements XOF via **PayDunya**, paiements NGN via **Paystack**. Clés API dans `.env`.

---

## DESIGN — style Stripe / 21st.dev

- Inspiration directe : **stripe.com** et les composants **21st.dev** — beaucoup de blanc, grilles aérées, typographie soignée, sections bien rythmées
- Fond blanc `#FFFFFF`, primaire bleu `#0048AE`, texte `#0A0A0A`, gris secondaire `#6B7280`
- **Zéro gradient, zéro shadow** : structure par bordures fines `border-gray-200`, fonds gris très clair `#F9FAFB` pour alterner les sections
- Police **Inter**, gros titres `font-bold tracking-tight`, beaucoup d'espace blanc
- **Icônes SVG inline uniquement** (style outline 1.5px). Inclure des **icônes SVG simplifiées des opérateurs et banques** : MTN (cercle jaune + lettres), Moov (bleu), Celtiis, et logos texte des banques nigérianes (GTBank, Access Bank, Zenith, UBA, First Bank, Opay, Palmpay, Kuda)
- Mobile-first, responsive partout

---

## CONTENUS — règle absolue

Tous les textes doivent être **rédigés entièrement, naturels et concrets** — pas de lorem ipsum, pas de phrases creuses qui sonnent « générées » (interdits : « solution innovante », « révolutionner », « expérience inégalée », « dans un monde où... »). Écris comme une vraie entreprise béninoise qui parle simplement à ses clients. Exemples de ton à suivre :

- Hero : « **Envoyez vos Naira, recevez du FCFA. Simple et rapide.** Vous vendez au Nigeria et vivez au Bénin ? Vous payez un fournisseur à Lagos ? GoChange convertit votre argent au vrai taux du jour, directement sur votre Mobile Money ou votre compte bancaire. »
- Comment ça marche : « 1. Créez votre compte en 2 minutes. 2. Déposez en FCFA (MTN, Moov, Celtiis) ou en Naira (carte, virement). 3. Échangez au taux affiché — ce que vous voyez, c'est ce que vous recevez. 4. Retirez sur votre compte bancaire nigérian ou votre Mobile Money. »
- Pourquoi nous : « Le nom du bénéficiaire s'affiche avant chaque transfert — impossible de se tromper de compte. » / « Support WhatsApp 7j/7, des humains qui répondent. » / « Frais affichés avant validation, jamais de surprise. »

Rédige TOUTES les pages avec ce niveau de contenu réel (FAQ avec 10 vraies questions/réponses, CGU et politique de confidentialité complètes adaptées au Bénin/Nigeria, page À propos mentionnant ASITECH SOLUTION, Parakou).

---

## SITEMAP — toutes les pages

**Public :**
- `/` Landing complète : navbar, hero + simulateur de conversion en direct, bandeau des moyens de paiement (icônes MTN, Moov, Celtiis, GTBank, Access, Zenith, UBA, Opay...), Comment ça marche (4 étapes), Services, Pourquoi nous (6 arguments), Taux du jour, Témoignages (3, réalistes), FAQ (accordéon), CTA « Commencer maintenant », footer complet
- `/taux` — page des taux NGN⇄XOF avec historique simple
- `/faq`, `/a-propos`, `/contact` (formulaire + WhatsApp), `/cgu`, `/confidentialite`
- `/inscription`, `/connexion`, `/mot-de-passe-oublie`, vérification email

**Connecté :**
- `/dashboard` — vue détaillée : cartes soldes NGN et XOF, taux du jour, niveau KYC actuel + limites restantes du jour (barre de progression), boutons Déposer / Échanger / Retirer, graphique simple des 30 derniers jours (volume échangé), tableau des 10 dernières transactions (type, montant, statut, date), alertes (ex. « Passez au niveau 2 pour augmenter vos limites »)
- `/deposer` (choix devise → PayDunya ou Paystack)
- `/echanger` (calcul en direct, taux figé à la validation)
- `/retirer` (XOF : Mobile Money / NGN : banque avec **résolution du nom du titulaire via Paystack `bank/resolve` + confirmation obligatoire**)
- `/transactions` — historique complet filtrable + export CSV
- `/beneficiaires` — comptes bancaires et numéros Momo enregistrés
- `/profil` — infos personnelles, changement de mot de passe, **section KYC** (voir ci-dessous)
- `/parametres` — notifications email, langue (FR/EN), suppression de compte

**Admin (Django admin personnalisé) :** taux & frais, utilisateurs, validation des documents KYC, approbation des retraits, dépôts/échanges/retraits, statistiques.

**SEO / technique :**
- `robots.txt` (autoriser pages publiques, bloquer /dashboard, /admin, pages connectées)
- `sitemap.xml` généré par Django (`django.contrib.sitemaps`) avec toutes les pages publiques
- Balises meta + Open Graph sur chaque page publique, titres uniques, domaine canonique **https://gochange.store**

---

## KYC — 3 NIVEAUX avec limites

Modèle `KYCProfile` lié à l'utilisateur, statut par niveau (non soumis / en attente / approuvé / rejeté), validation par l'admin.

| Niveau | Conditions | Limite dépôt/jour | Limite retrait/jour |
|---|---|---|---|
| **L1** | Email + téléphone vérifiés (automatique à l'inscription) | **50 000 FCFA** (~130 000 NGN) | **50 000 FCFA** |
| **L2** | Pièce d'identité (CNI, passeport ou CIP) + selfie — upload, validation admin | **500 000 FCFA** (~1 300 000 NGN) | **500 000 FCFA** |
| **L3** | L2 + justificatif d'adresse ou registre de commerce (pour les pros) | **2 000 000 FCFA/jour** | **2 000 000 FCFA/jour** |

- Les limites sont stockées en base (modifiables par l'admin), vérifiées côté serveur avant chaque dépôt/retrait, avec compteur journalier remis à zéro à minuit
- Page `/profil` : affichage clair du niveau actuel, des limites, et bouton « Augmenter mes limites » → formulaire d'upload des documents
- Email automatique à l'approbation/rejet d'un niveau

---

## FLUX DE PAIEMENT (résumé)

**Dépôt XOF (PayDunya)** : choix opérateur (MTN MoMo, Moov Money, Celtiis Cash) → facture `checkout-invoice/create` → redirection → crédit du solde UNIQUEMENT après confirmation webhook IPN.

**Dépôt NGN (Paystack)** : `transaction/initialize` (kobo) → checkout → crédit après `transaction/verify` + webhook signé.

**Échange** : montant × taux − frais (% en admin), opération atomique, taux figé.

**Retrait XOF** : opérateur + numéro → décaissement PayDunya.

**Retrait NGN** : liste banques (`GET /bank?currency=NGN`) → numéro de compte 10 chiffres → **appel `GET /bank/resolve` → affichage automatique du NOM DU TITULAIRE** → case « Je confirme le bénéficiaire » obligatoire → `transferrecipient` + `transfer` → statut final via webhook. Clé secrète jamais exposée au frontend (endpoint Django proxy).

---

## MODÈLES & SÉCURITÉ

`CustomUser`, `Wallet` (balance_ngn, balance_xof — `select_for_update`), `ExchangeRate`, `KYCProfile`, `KYCDocument`, `DailyLimit`, `Deposit`, `ExchangeTransaction`, `Withdrawal`, `Beneficiary`, `WebhookLog`.

Sécurité : montants en `DecimalField`, webhooks idempotents, CSRF, rate limiting login/paiements, journalisation des appels API, mode test/sandbox des deux providers via `.env`.

---

## LIVRABLES

1. Projet Django complet prêt à lancer (`requirements.txt`, migrations, README en français)
2. Toutes les pages du sitemap, avec contenus réels intégralement rédigés
3. Intégrations PayDunya + Paystack fonctionnelles en mode test (webhooks inclus)
4. robots.txt + sitemap.xml + meta SEO pour gochange.store
5. Seed : taux par défaut, limites KYC L1/L2/L3, compte admin