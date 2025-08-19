# BRVM Daily BOC Scraper

Ce projet automatise la récupération, l'extraction et l'archivage des données des Bulletins Officiels de la Cote (BOC) de la BRVM vers un Google Sheet.

## 🚀 Configuration Initiale

Suivez ces étapes pour rendre le projet opérationnel.

### Étape 1 : Créer un Dépôt GitHub

1.  Créez un nouveau dépôt sur GitHub. **Il est fortement recommandé de le rendre `Privé`** pour protéger vos informations de configuration.
2.  Ajoutez les deux fichiers suivants à ce dépôt :
    *   `main.py` (le script Python)
    *   `.github/workflows/daily_run.yml` (le fichier d'automatisation)

### Étape 2 : Configurer le Compte de Service Google

Ce script utilise un compte de service pour accéder à votre Google Sheet de manière sécurisée sans avoir besoin de votre mot de passe.

1.  **Créez un Compte de Service :**
    *   Allez sur la [page des comptes de service de Google Cloud](https://console.cloud.google.com/iam-admin/serviceaccounts).
    *   Sélectionnez votre projet (ou créez-en un nouveau).
    *   Cliquez sur **"+ CRÉER UN COMPTE DE SERVICE"**.
    *   Donnez-lui un nom (ex: `brvm-automation-bot`) et une description. Cliquez sur **"CRÉER ET CONTINUER"**.
    *   Pour le rôle, choisissez **"Éditeur"** (`Editor`). Cliquez sur **"CONTINUER"**, puis sur **"OK"**.

2.  **Générez une Clé JSON :**
    *   Trouvez votre nouveau compte de service dans la liste, cliquez sur les trois points (`⋮`) à droite, puis sur **"Gérer les clés"**.
    *   Cliquez sur **"AJOUTER UNE CLÉ"** -> **"Créer une nouvelle clé"**.
    *   Choisissez le format **JSON** et cliquez sur **"CRÉER"**.
    *   Un fichier `.json` sera téléchargé sur votre ordinateur. **Conservez ce fichier en lieu sûr, c'est votre mot de passe !**

3.  **Partagez votre Google Sheet :**
    *   Ouvrez le fichier JSON téléchargé et copiez l'adresse e-mail qui se trouve à la ligne `"client_email"` (elle ressemble à `...@...iam.gserviceaccount.com`).
    *   Allez sur votre [Google Sheet](https://docs.google.com/spreadsheets/d/1EGXyg13ml8a9zr4OaUPnJN3i-rwVO2uq330yfxJXnSM/edit).
    *   Cliquez sur **"Partager"** en haut à droite.
    *   Collez l'adresse e-mail du compte de service, donnez-lui les droits **"Éditeur"**, et cliquez sur **"Envoyer"**.

### Étape 3 : Ajouter la Clé JSON aux Secrets GitHub

1.  Dans votre dépôt GitHub, allez dans **`Settings`** -> **`Secrets and variables`** -> **`Actions`**.
2.  Cliquez sur le bouton **`New repository secret`**.
3.  Dans le champ **`Name`**, entrez exactement : `GSPREAD_SERVICE_ACCOUNT`
4.  Dans le champ **`Value`**, ouvrez le fichier `.json` que vous avez téléchargé, copiez **tout son contenu** et collez-le dans ce champ.
5.  Cliquez sur **`Add secret`**.

### Étape 4 : Activer et Tester le Workflow

1.  Allez dans l'onglet **`Actions`** de votre dépôt GitHub.
2.  Sur la gauche, vous devriez voir "BRVM Daily BOC Scraper". Cliquez dessus.
3.  Vous verrez un message "This workflow has a workflow\_dispatch event trigger". Cliquez sur le bouton **`Run workflow`** pour lancer manuellement le script une première fois et vérifier que tout fonctionne.
4.  Vous pouvez suivre l'exécution en temps réel. Si tout est bien configuré, le script s'exécutera sans erreur.

Le script tournera désormais automatiquement tous les jours à 07h00 UTC.
