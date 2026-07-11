"""
Script d'initialisation et de migration de la base de données.
Crée les tables, ajoute les nouvelles colonnes si nécessaire,
un compte admin par défaut, et les paramètres initiaux.
Utilisation : python init_db.py
"""
from app import app, run_migrations
from models import db, User, Parametres
from werkzeug.security import generate_password_hash
from sqlalchemy import text, inspect
import os


def migrate_db():
    """Ajoute les nouvelles colonnes si elles n'existent pas (migration douce SQLite)."""
    engine = db.engine
    inspector = inspect(engine)

    # ── Migration table parametres ───────────────────────────
    if 'parametres' in inspector.get_table_names():
        existing = [c['name'] for c in inspector.get_columns('parametres')]
        new_cols = [
            ("adresse",         "TEXT"),
            ("telephone",       "VARCHAR(50)"),
            ("site_web",        "VARCHAR(200)"),
            ("message_recu",    "VARCHAR(300) DEFAULT 'Merci pour votre achat !'"),
            ("seuil_stock_bas", "INTEGER DEFAULT 5"),
            ("pagination",      "INTEGER DEFAULT 20"),
        ]
        with engine.connect() as conn:
            for col_name, col_def in new_cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE parametres ADD COLUMN {col_name} {col_def}"))
                    print(f"  ✓ Colonne 'parametres.{col_name}' ajoutée.")
            conn.commit()

    # ── Migration table audit_logs ───────────────────────────
    if 'audit_logs' in inspector.get_table_names():
        existing = [c['name'] for c in inspector.get_columns('audit_logs')]
        if 'ip_address' not in existing:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN ip_address VARCHAR(45)"))
                conn.commit()
            print("  ✓ Colonne 'audit_logs.ip_address' ajoutée.")

    # ── Migrations v2 : devises par produit ─────────────────
    run_migrations()


def init_database():
    with app.app_context():
        # Créer toutes les tables (nouvelles tables uniquement)
        db.create_all()
        print("✓ Tables vérifiées/créées.")

        # Migrations des tables existantes
        migrate_db()

        # Compte admin par défaut
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

        # Paramètres par défaut
        params = Parametres.query.first()
        if not params:
            params = Parametres(
                nom_magasin='Mon Magasin',
                logo=None,
                adresse=None,
                telephone=None,
                site_web=None,
                message_recu='Merci pour votre achat !',
                devise_active='FC',
                taux_change_usd_fc=2800.0,
                seuil_stock_bas=5,
                pagination=20,
            )
            db.session.add(params)
            print("✓ Paramètres par défaut créés.")
        else:
            if not params.message_recu:
                params.message_recu = 'Merci pour votre achat !'
            if not params.seuil_stock_bas:
                params.seuil_stock_bas = 5
            if not params.pagination:
                params.pagination = 20
            print("  Paramètres existants — valeurs par défaut appliquées si manquantes.")

        db.session.commit()
        print("\n✅ Base de données initialisée avec succès.")
        print("   ⚠️  Changez le mot de passe admin après la première connexion.")


if __name__ == '__main__':
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    init_database()
