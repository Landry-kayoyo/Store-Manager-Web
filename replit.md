# Gestion de Magasin

Application web interne de gestion de magasin (matériel informatique, accessoires, etc.) — Flask + SQLite, déployable sur PythonAnywhere.

## Run & Operate

```bash
# 1. Installer les dépendances
cd flask-store && pip install -r requirements.txt

# 2. Initialiser la base de données (une seule fois)
python init_db.py

# 3. Lancer l'application
python app.py
```

Accès : [http://localhost:5000](http://localhost:5000)  
Compte admin par défaut : `admin@magasin.com` / `admin123`

## Stack

- **Backend** : Flask 3.0 (Python)
- **Frontend** : HTML/CSS/JavaScript vanilla + Chart.js (CDN)
- **Base de données** : SQLite via Flask-SQLAlchemy
- **Auth** : Sessions Flask + werkzeug.security (hash bcrypt)
- **Images** : Pillow (redimensionnement auto 300×300)
- **Structure WSGI** : Compatible PythonAnywhere (`app.py` comme point d'entrée)

## Where things live

- `flask-store/app.py` — toutes les routes Flask
- `flask-store/models.py` — modèles SQLAlchemy (User, Produit, Vente, Promotion, AuditLog, Parametres)
- `flask-store/templates/` — templates Jinja2
- `flask-store/static/css/style.css` — palette vert forêt / or, responsive
- `flask-store/static/js/caisse.js` — logique panier côté client (JSON fetch)
- `flask-store/static/js/dashboard.js` — graphiques Chart.js via `/api/dashboard-stats`
- `flask-store/static/uploads/` — photos de profil et logos (gitkeep inclus)

## Architecture decisions

- Auth manuelle via Flask session (pas Flask-Login) — dépendance minimale
- Journal d'audit en BDD, non modifiable même par l'admin
- L'historique des ventes snapshot la devise et le taux au moment de la vente (jamais recalculé)
- API `/api/dashboard-stats` chargée en AJAX pour ne pas bloquer l'affichage initial
- Pagination obligatoire (20 items/page) sur toutes les listes

## User preferences

- Stack : Python Flask + SQLite (pour PythonAnywhere)
- Langue de l'interface : Français
