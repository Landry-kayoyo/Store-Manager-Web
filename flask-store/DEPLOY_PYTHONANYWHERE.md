# Déploiement sur PythonAnywhere — Guide complet

Compte PythonAnywhere : **katangatech**  
Dépôt GitHub : `https://github.com/Landry-kayoyo/Store-Manager-Web`

---

## ÉTAPE 1 — Ouvrir une console Bash

Sur le Dashboard PythonAnywhere, cliquez sur **`$ Bash`** dans la section "New console".

---

## ÉTAPE 2 — Cloner le dépôt

```bash
cd ~
git clone https://github.com/Landry-kayoyo/Store-Manager-Web.git
ls Store-Manager-Web/flask-store/
```

Vous devriez voir : `app.py`, `models.py`, `requirements.txt`, `templates/`, `static/`, etc.

---

## ÉTAPE 3 — Créer un environnement virtuel Python

```bash
cd ~/Store-Manager-Web
python3.11 -m venv venv
```

> Si Python 3.11 n'est pas disponible, essayez `python3.10`.

---

## ÉTAPE 4 — Installer les dépendances

```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r flask-store/requirements.txt
```

Attendez la fin de l'installation (environ 1 minute).

---

## ÉTAPE 5 — Initialiser la base de données

```bash
cd ~/Store-Manager-Web/flask-store
python init_db.py
```

Vous devriez voir :
```
✓ Tables vérifiées/créées.
✓ Compte admin créé (admin@magasin.com / admin123).
✓ Paramètres par défaut créés.
✅ Base de données initialisée avec succès.
```

---

## ÉTAPE 6 — Configurer l'application web

1. Allez dans l'onglet **Web** sur PythonAnywhere
2. Cliquez sur **"Add a new web app"**
3. Cliquez sur **"Next"**
4. Choisissez **"Manual configuration"** (pas Flask — on configure manuellement)
5. Choisissez **Python 3.11**
6. Cliquez sur **"Next"** puis **"Next"**

---

## ÉTAPE 7 — Configurer le fichier WSGI

Sur la page de configuration de votre web app :

1. Cherchez la section **"Code"**
2. Cliquez sur le lien du **fichier WSGI** (ex: `/var/www/katangatech_pythonanywhere_com_wsgi.py`)
3. **Effacez tout le contenu** du fichier
4. Collez exactement ce code :

```python
import sys
import os

# Chemin vers le dossier de l'application
path = '/home/katangatech/Store-Manager-Web/flask-store'
if path not in sys.path:
    sys.path.insert(0, path)

# Clé secrète — CHANGEZ cette valeur !
os.environ['SECRET_KEY'] = 'mettez-une-longue-cle-secrete-ici-au-moins-32-caracteres'

from app import app as application
```

5. Cliquez sur **Save**

---

## ÉTAPE 8 — Configurer les fichiers statiques

Toujours dans l'onglet **Web**, section **"Static files"** :

Cliquez **"Enter URL"** et ajoutez ces deux lignes :

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/katangatech/Store-Manager-Web/flask-store/static` |

---

## ÉTAPE 9 — Configurer l'environnement virtuel

Dans la section **"Virtualenv"** de l'onglet Web :

Entrez le chemin :
```
/home/katangatech/Store-Manager-Web/venv
```

Cliquez sur la coche ✓ pour valider.

---

## ÉTAPE 10 — Recharger l'application

Cliquez sur le bouton vert **"Reload katangatech.pythonanywhere.com"**

Attendez quelques secondes, puis ouvrez :
```
https://katangatech.pythonanywhere.com
```

---

## Connexion initiale

| Email | Mot de passe | Rôle |
|-------|-------------|------|
| admin@magasin.com | admin123 | Admin |

⚠️ **Changez immédiatement le mot de passe admin** après la première connexion.

---

## En cas d'erreur — Consulter les logs

Dans l'onglet **Web**, section **"Log files"** :

- **Error log** : erreurs Python (500, imports, etc.)
- **Access log** : toutes les requêtes HTTP

```bash
# Ou depuis la console Bash :
tail -20 /var/log/katangatech.pythonanywhere.com.error.log
```

---

## Mettre à jour l'application (après modifications)

```bash
cd ~/Store-Manager-Web
git pull origin main
source venv/bin/activate
pip install -r flask-store/requirements.txt   # si requirements changés
cd flask-store && python init_db.py            # si modèles changés
```

Puis rechargez depuis l'onglet Web.

---

## Structure dans PythonAnywhere

```
/home/katangatech/
├── Store-Manager-Web/        ← dépôt GitHub
│   ├── flask-store/
│   │   ├── app.py
│   │   ├── models.py
│   │   ├── init_db.py
│   │   ├── database.db       ← créé par init_db.py
│   │   ├── requirements.txt
│   │   ├── wsgi.py
│   │   ├── static/
│   │   │   ├── css/
│   │   │   ├── js/
│   │   │   └── uploads/      ← photos & logos
│   │   └── templates/
│   └── venv/                 ← environnement virtuel Python
```
