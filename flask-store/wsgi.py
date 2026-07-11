"""
Fichier WSGI pour PythonAnywhere.
Ce fichier est utilisé par le serveur web PythonAnywhere pour démarrer l'application.

NE PAS modifier le nom de la variable `application` — PythonAnywhere l'exige.
"""
import sys
import os

# Chemin vers le dossier flask-store dans le dépôt cloné
path = '/home/katangatech/Store-Manager-Web/flask-store'
if path not in sys.path:
    sys.path.insert(0, path)

# Clé secrète Flask — CHANGEZ cette valeur par quelque chose d'aléatoire et long
os.environ.setdefault('SECRET_KEY', 'CHANGEZ-CETTE-CLE-PAR-UNE-VALEUR-SECRETE-LONGUE')

from app import app as application  # noqa
