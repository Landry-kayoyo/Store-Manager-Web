"""
Script d'initialisation de la base de données.
Crée les tables, un compte admin par défaut, et les paramètres initiaux.
Utilisation : python init_db.py
"""
from app import app
from models import db, User, Parametres
from werkzeug.security import generate_password_hash
import os


def init_database():
    with app.app_context():
        # Créer toutes les tables
        db.create_all()
        print("✓ Tables créées.")

        # Créer le compte admin par défaut si absent
        if not User.query.filter_by(email='admin@magasin.com').first():
            admin = User(
                nom='Administrateur',
                email='admin@magasin.com',
                mot_de_passe_hash=generate_password_hash('admin123'),
                role='admin',
                actif=True,
            )
            db.session.add(admin)
            print("✓ Compte admin créé (admin@magasin.com / admin123).")
        else:
            print("  Admin existant, ignoré.")

        # Créer les paramètres par défaut si absents
        if not Parametres.query.first():
            params = Parametres(
                nom_magasin='Mon Magasin',
                logo=None,
                devise_active='FC',
                taux_change_usd_fc=2800.0,
            )
            db.session.add(params)
            print("✓ Paramètres par défaut créés.")
        else:
            print("  Paramètres existants, ignorés.")

        db.session.commit()
        print("\n✅ Base de données initialisée avec succès.")
        print("   ⚠️  Changez le mot de passe admin après la première connexion.")


if __name__ == '__main__':
    # Créer le dossier uploads si nécessaire
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    init_database()
