"""
Modèles SQLAlchemy pour l'application de gestion de magasin.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='agent')  # 'admin' ou 'agent'
    actif = db.Column(db.Boolean, default=True, nullable=False)
    photo_profil = db.Column(db.String(200), nullable=True)
    derniere_connexion = db.Column(db.DateTime, nullable=True)

    ventes = db.relationship('Vente', backref='agent', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.email}>'


class Produit(db.Model):
    __tablename__ = 'produits'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(100), nullable=False, index=True)
    prix = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)

    lignes_vente = db.relationship('LigneVente', backref='produit', lazy='dynamic')
    promotions = db.relationship('Promotion', backref='produit', lazy='dynamic', foreign_keys='Promotion.produit_id')

    def __repr__(self):
        return f'<Produit {self.nom}>'


class Vente(db.Model):
    __tablename__ = 'ventes'
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    total = db.Column(db.Float, nullable=False)
    devise = db.Column(db.String(10), nullable=False)
    taux_change_utilise = db.Column(db.Float, nullable=False, default=1.0)
    numero_recu = db.Column(db.String(50), unique=True, nullable=False)

    lignes = db.relationship('LigneVente', backref='vente', lazy='dynamic',
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Vente {self.numero_recu}>'


class LigneVente(db.Model):
    __tablename__ = 'lignes_vente'
    id = db.Column(db.Integer, primary_key=True)
    vente_id = db.Column(db.Integer, db.ForeignKey('ventes.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=True)
    nom_produit = db.Column(db.String(200), nullable=False)   # instantané au moment de la vente
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)       # prix effectif (après promo)
    prix_original = db.Column(db.Float, nullable=True)        # prix avant promo
    promo_pct = db.Column(db.Float, nullable=True)            # % de réduction appliqué
    sous_total = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<LigneVente {self.nom_produit} x{self.quantite}>'


class Promotion(db.Model):
    __tablename__ = 'promotions'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=True)
    categorie = db.Column(db.String(100), nullable=True)  # si non null, s'applique à toute la catégorie
    pourcentage = db.Column(db.Float, nullable=False)     # ex : 10 pour 10%
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f'<Promotion {self.pourcentage}% du {self.date_debut} au {self.date_fin}>'


class Parametres(db.Model):
    __tablename__ = 'parametres'
    id = db.Column(db.Integer, primary_key=True)
    # Identité
    nom_magasin = db.Column(db.String(200), default='Mon Magasin', nullable=False)
    logo = db.Column(db.String(200), nullable=True)
    # Contact (affiché sur les reçus)
    adresse = db.Column(db.Text, nullable=True)
    telephone = db.Column(db.String(50), nullable=True)
    site_web = db.Column(db.String(200), nullable=True)
    # Reçu
    message_recu = db.Column(db.String(300), default='Merci pour votre achat !', nullable=False)
    # Devise
    devise_active = db.Column(db.String(10), default='FC', nullable=False)  # 'FC' ou 'USD'
    taux_change_usd_fc = db.Column(db.Float, default=2800.0, nullable=False)
    # Seuils opérationnels
    seuil_stock_bas = db.Column(db.Integer, default=5, nullable=False)
    pagination = db.Column(db.Integer, default=20, nullable=False)

    def __repr__(self):
        return f'<Parametres {self.nom_magasin}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, nullable=True)
    ancienne_valeur = db.Column(db.Text, nullable=True)
    nouvelle_valeur = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    date_heure = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action} at {self.date_heure}>'
