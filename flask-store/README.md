# Gestion de Magasin — Application Flask

Application web interne de gestion de magasin (matériel informatique, accessoires, et autres).

## Démarrage rapide

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Initialiser la base de données

```bash
python init_db.py
```

Ceci crée la base de données `database.db`, les tables, et un compte admin par défaut.

### 3. Lancer l'application

```bash
python app.py
```

L'application sera accessible à [http://localhost:5000](http://localhost:5000).

## Compte par défaut

| Email                | Mot de passe | Rôle  |
|----------------------|-------------|-------|
| admin@magasin.com    | admin123    | Admin |

⚠️ **Changez le mot de passe admin après la première connexion** via `/agents`.

## Déploiement sur PythonAnywhere

1. Uploadez tous les fichiers dans votre répertoire sur PythonAnywhere
2. Installez les dépendances : `pip install -r requirements.txt --user`
3. Lancez l'initialisation : `python init_db.py`
4. Dans le dashboard PythonAnywhere, configurez une application WSGI :
   - **Source code** : chemin vers votre dossier
   - **WSGI file** : pointez vers `app.py`, en exposant `app` comme objet WSGI
   - Ajoutez la variable d'environnement `SECRET_KEY` avec une valeur secrète

## Structure des fichiers

```
flask-store/
├── app.py              # Point d'entrée WSGI — toutes les routes
├── models.py           # Modèles SQLAlchemy (User, Produit, Vente, etc.)
├── init_db.py          # Script d'initialisation de la BDD
├── requirements.txt    # Dépendances Python
├── database.db         # Base SQLite (créée par init_db.py)
├── templates/          # Templates Jinja2
│   ├── base.html       # Layout principal avec sidebar
│   ├── login.html
│   ├── dashboard.html  # Vue agent ou admin selon le rôle
│   ├── stock.html
│   ├── caisse.html     # Caisse enregistreuse
│   ├── recu.html       # Reçu imprimable (auto-print)
│   ├── historique.html
│   ├── agents.html     # Admin : gestion des agents
│   ├── statistiques.html
│   ├── promotions.html
│   ├── parametres.html # Nom du magasin, logo, devise
│   ├── audit.html      # Journal d'audit
│   ├── profil.html
│   └── errors/         # 403, 404, 500
└── static/
    ├── css/style.css
    ├── js/
    │   ├── main.js
    │   ├── caisse.js   # Logique panier côté client
    │   └── dashboard.js # Charts Chart.js (CDN)
    └── uploads/        # Photos de profil et logos
```

## Fonctionnalités

### Agents
- Consultation du stock (lecture seule, alertes stock bas)
- Caisse enregistreuse avec promotions automatiques
- Génération de reçus imprimables
- Historique de ses propres ventes
- Gestion de sa photo de profil

### Administrateurs
- Toutes les fonctionnalités agents +
- Gestion complète des produits (CRUD)
- Gestion des comptes agents
- Dashboard avec KPIs, graphiques Chart.js
- Gestion des promotions (par produit ou catégorie)
- Paramètres : nom du magasin, logo, devise (FC / USD), taux de change
- Journal d'audit complet (non modifiable)

## Variables d'environnement

| Variable     | Description              | Défaut (dev only)         |
|-------------|--------------------------|---------------------------|
| `SECRET_KEY` | Clé secrète Flask        | Valeur par défaut non sûre |

Définissez toujours `SECRET_KEY` en production.
