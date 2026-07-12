"""
Modèles SQLAlchemy — Gestion de magasin.
Supporte les devises mixtes FC/USD par produit et l'accès concurrent multi-agents.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()


# ── WAL mode pour SQLite : permet les lectures concurrentes pendant les écritures ──
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")   # 64 Mo de cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")   # attend 5 s avant d'échouer
        cursor.close()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='agent')   # 'admin' | 'agent'
    actif = db.Column(db.Boolean, default=True, nullable=False)
    photo_profil = db.Column(db.String(200), nullable=True)
    derniere_connexion = db.Column(db.DateTime, nullable=True)

    ventes = db.relationship('Vente', backref='agent', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.email}>'


class Produit(db.Model):
    __tablename__ = 'produits'
    __table_args__ = (
        db.Index('ix_produits_categorie_nom', 'categorie', 'nom'),
    )
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(100), nullable=False, index=True)
    prix = db.Column(db.Float, nullable=False)
    # Devise dans laquelle le prix est saisi : 'FC' ou 'USD'
    devise = db.Column(db.String(10), nullable=False, default='FC')
    stock = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)

    lignes_vente = db.relationship('LigneVente', backref='produit', lazy='dynamic')
    promotions = db.relationship(
        'Promotion', backref='produit', lazy='dynamic',
        foreign_keys='Promotion.produit_id'
    )

    def prix_en(self, devise_cible, taux_usd_fc):
        """Retourne le prix converti dans devise_cible selon taux_usd_fc (1 USD = X FC)."""
        if self.devise == devise_cible:
            return self.prix
        if self.devise == 'USD' and devise_cible == 'FC':
            return round(self.prix * taux_usd_fc, 4)
        if self.devise == 'FC' and devise_cible == 'USD':
            return round(self.prix / taux_usd_fc, 4)
        return self.prix

    def __repr__(self):
        return f'<Produit {self.nom}>'


class Vente(db.Model):
    __tablename__ = 'ventes'
    __table_args__ = (
        db.Index('ix_ventes_agent_date', 'agent_id', 'date'),
    )
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    total = db.Column(db.Float, nullable=False)           # total dans la devise ci-dessous
    devise = db.Column(db.String(10), nullable=False)     # devise du total
    taux_change_utilise = db.Column(db.Float, nullable=False, default=1.0)
    numero_recu = db.Column(db.String(50), unique=True, nullable=False)
    # True si la vente contient des produits de devises différentes
    multi_devises = db.Column(db.Boolean, default=False, nullable=False)

    lignes = db.relationship('LigneVente', backref='vente', lazy='dynamic',
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Vente {self.numero_recu}>'


class LigneVente(db.Model):
    __tablename__ = 'lignes_vente'
    id = db.Column(db.Integer, primary_key=True)
    vente_id = db.Column(db.Integer, db.ForeignKey('ventes.id'), nullable=False, index=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=True)
    nom_produit = db.Column(db.String(200), nullable=False)   # instantané
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)       # prix effectif, converti dans la devise de la vente
    prix_original = db.Column(db.Float, nullable=True)        # prix avant promo (dans devise vente)
    promo_pct = db.Column(db.Float, nullable=True)
    sous_total = db.Column(db.Float, nullable=False)          # dans la devise de la vente
    # Devise originale du produit au moment de la vente
    devise_produit = db.Column(db.String(10), nullable=True)
    # Prix dans la devise d'origine (avant conversion)
    prix_unitaire_origine = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<LigneVente {self.nom_produit} x{self.quantite}>'


class Promotion(db.Model):
    __tablename__ = 'promotions'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=True)
    categorie = db.Column(db.String(100), nullable=True, index=True)
    pourcentage = db.Column(db.Float, nullable=False)
    date_debut = db.Column(db.Date, nullable=False, index=True)
    date_fin = db.Column(db.Date, nullable=False, index=True)

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
    # Devise par défaut de la caisse (peut différer des devises des produits)
    devise_active = db.Column(db.String(10), default='FC', nullable=False)
    # Taux de change de référence configuré par l'admin
    taux_change_usd_fc = db.Column(db.Float, default=2800.0, nullable=False)
    # Opérationnel
    seuil_stock_bas = db.Column(db.Integer, default=5, nullable=False)
    pagination = db.Column(db.Integer, default=20, nullable=False)

    def __repr__(self):
        return f'<Parametres {self.nom_magasin}>'


class HistoriqueTaux(db.Model):
    """Historique immuable des taux de change. Chaque modification crée un enregistrement."""
    __tablename__ = 'historique_taux'
    id = db.Column(db.Integer, primary_key=True)
    taux = db.Column(db.Float, nullable=False)
    date_debut = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    note = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<HistoriqueTaux {self.taux} FC/$ depuis {self.date_debut}>'


class ChatMessage(db.Model):
    """Messages entre agents et admin (support interne)."""
    __tablename__ = 'chat_messages'
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contenu     = db.Column(db.Text, nullable=False)
    date_envoi  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    lu          = db.Column(db.Boolean, default=False, nullable=False)

    sender   = db.relationship('User', foreign_keys=[sender_id],   backref='messages_envoyes')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='messages_recus')

    def __repr__(self):
        return f'<ChatMessage {self.sender_id}→{self.receiver_id} {self.date_envoi:%H:%M}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    detail = db.Column(db.Text, nullable=True)
    ancienne_valeur = db.Column(db.Text, nullable=True)
    nouvelle_valeur = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    date_heure = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action} at {self.date_heure}>'
