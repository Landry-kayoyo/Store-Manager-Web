"""
Fichier WSGI pour PythonAnywhere.
NE PAS modifier le nom de la variable `application`.
"""
import sys
import os

# Chemin vers le dossier flask-store dans le dépôt cloné
path = '/home/katangatech/Store-Manager-Web/flask-store'
if path not in sys.path:
    sys.path.insert(0, path)

# Clé secrète Flask — CHANGEZ cette valeur par quelque chose d'aléatoire et long
os.environ.setdefault('SECRET_KEY', 'CHANGEZ-CETTE-CLE-PAR-UNE-VALEUR-SECRETE-LONGUE')

from app import app as application, run_migrations  # noqa

# Appliquer les migrations au démarrage du worker WSGI
with application.app_context():
    try:
        from models import db
        db.create_all()
        run_migrations()
    except Exception as _e:
        import logging
        logging.warning(f"WSGI startup migration warning: {_e}")
