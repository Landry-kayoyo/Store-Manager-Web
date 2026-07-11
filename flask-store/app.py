"""
Application Flask — Gestion de magasin interne.
Point d'entrée WSGI compatible PythonAnywhere.
Supporte les devises mixtes FC/USD par produit, accès concurrent multi-agents (WAL).
"""
import os
import io
import csv
import json
import logging
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort, send_from_directory,
                   Response)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from sqlalchemy.orm import joinedload

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Clé secrète — TOUJOURS définir SECRET_KEY en production
_secret = os.environ.get('SECRET_KEY', '')
if not _secret:
    _secret = 'dev-fallback-key-CHANGE-IN-PRODUCTION'
    logging.warning("⚠️  SECRET_KEY non définie ! Utilisez la variable d'environnement SECRET_KEY en production.")
app.config['SECRET_KEY'] = _secret

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {'check_same_thread': False, 'timeout': 20},
}
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max

# ── Sécurité des cookies de session ──────────────────────
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get('SECRET_KEY'):
    app.config['SESSION_COOKIE_SECURE'] = True

# ── CSRF (Flask-WTF) ─────────────────────────────────────
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 heure
csrf = CSRFProtect(app)

# ── Rate Limiter ─────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DEVISES = ['FC', 'USD']

from models import db, User, Produit, Vente, LigneVente, Promotion, Parametres, AuditLog
db.init_app(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ──────────────────────────────────────────────────────────
# Migration douce : ajouter les nouvelles colonnes si absentes
# ──────────────────────────────────────────────────────────
def run_migrations():
    """Ajoute toutes les colonnes manquantes sans casser la DB existante."""
    import sqlite3
    db_path = os.path.join(BASE_DIR, 'database.db')
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # ── Parametres ──────────────────────────────────────────
    cur.execute("PRAGMA table_info(parametres)")
    pcols = {row[1] for row in cur.fetchall()}
    _param_cols = [
        ('adresse',           "TEXT"),
        ('telephone',         "VARCHAR(50)"),
        ('site_web',          "VARCHAR(200)"),
        ('message_recu',      "VARCHAR(300) DEFAULT 'Merci pour votre achat !'"),
        ('devise_active',     "VARCHAR(10) NOT NULL DEFAULT 'FC'"),
        ('taux_change_usd_fc',"REAL NOT NULL DEFAULT 2800.0"),
        ('seuil_stock_bas',   "INTEGER NOT NULL DEFAULT 5"),
        ('pagination',        "INTEGER NOT NULL DEFAULT 20"),
    ]
    for col_name, col_def in _param_cols:
        if col_name not in pcols:
            cur.execute(f"ALTER TABLE parametres ADD COLUMN {col_name} {col_def}")
            app.logger.info(f"Migration : colonne parametres.{col_name} ajoutée.")

    # ── Produit.devise ───────────────────────────────────────
    cur.execute("PRAGMA table_info(produits)")
    cols = {row[1] for row in cur.fetchall()}
    if 'devise' not in cols:
        cur.execute("ALTER TABLE produits ADD COLUMN devise TEXT NOT NULL DEFAULT 'FC'")
        app.logger.info("Migration : colonne produits.devise ajoutée.")

    # ── Vente.multi_devises ──────────────────────────────────
    cur.execute("PRAGMA table_info(ventes)")
    vcols = {row[1] for row in cur.fetchall()}
    if 'multi_devises' not in vcols:
        cur.execute("ALTER TABLE ventes ADD COLUMN multi_devises INTEGER NOT NULL DEFAULT 0")
        app.logger.info("Migration : colonne ventes.multi_devises ajoutée.")

    # ── LigneVente ───────────────────────────────────────────
    cur.execute("PRAGMA table_info(lignes_vente)")
    lcols = {row[1] for row in cur.fetchall()}
    if 'devise_produit' not in lcols:
        cur.execute("ALTER TABLE lignes_vente ADD COLUMN devise_produit TEXT")
        app.logger.info("Migration : colonne lignes_vente.devise_produit ajoutée.")
    if 'prix_unitaire_origine' not in lcols:
        cur.execute("ALTER TABLE lignes_vente ADD COLUMN prix_unitaire_origine REAL")
        app.logger.info("Migration : colonne lignes_vente.prix_unitaire_origine ajoutée.")

    # ── AuditLog.ip_address ──────────────────────────────────
    cur.execute("PRAGMA table_info(audit_logs)")
    acols = {row[1] for row in cur.fetchall()}
    if 'ip_address' not in acols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN ip_address VARCHAR(45)")
        app.logger.info("Migration : colonne audit_logs.ip_address ajoutée.")

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────
# Décorateurs d'authentification
# ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────────────────
# Fonctions utilitaires
# ──────────────────────────────────────────────────────────
def get_params():
    """Retourne les paramètres du magasin (crée si absent)."""
    p = Parametres.query.first()
    if not p:
        p = Parametres()
        db.session.add(p)
        db.session.commit()
    return p


def format_montant(montant, devise=None):
    """Formate un montant selon la devise."""
    if devise is None:
        devise = get_params().devise_active
    if devise == 'FC':
        return f"{int(round(montant)):,} FC".replace(',', ' ')
    else:
        return f"${montant:,.2f}"


def convertir(montant, de_devise, vers_devise, taux_usd_fc):
    """Convertit un montant d'une devise à l'autre selon le taux configuré."""
    if de_devise == vers_devise:
        return montant
    if de_devise == 'USD' and vers_devise == 'FC':
        return round(montant * taux_usd_fc, 4)
    if de_devise == 'FC' and vers_devise == 'USD':
        return round(montant / taux_usd_fc, 4)
    return montant


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file, prefix='img', max_size=(300, 300)):
    """Vérifie, redimensionne et sauvegarde une image. Retourne le nom de fichier."""
    from PIL import Image, UnidentifiedImageError
    import uuid
    if not file or not allowed_file(file.filename):
        return None
    file.seek(0)
    try:
        probe = Image.open(file)
        probe.verify()
    except (UnidentifiedImageError, Exception):
        return None
    file.seek(0)
    try:
        img = Image.open(file)
        img = img.convert('RGB') if img.mode not in ('RGB', 'RGBA') else img
        img.thumbnail(max_size, Image.LANCZOS)
        ext = 'jpg' if img.mode == 'RGB' else 'png'
        filename = f"{prefix}_{uuid.uuid4().hex[:10]}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        img.save(filepath, quality=88, optimize=True)
        return filename
    except Exception as exc:
        app.logger.warning(f"save_image error: {exc}")
        return None


def delete_image(filename):
    if filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        except OSError:
            pass


def generate_numero_recu():
    """Génère un numéro de reçu unique : REC-YYYYMMDD-NNNNN."""
    today_str = datetime.utcnow().strftime('%Y%m%d')
    count = Vente.query.filter(
        Vente.numero_recu.like(f'REC-{today_str}-%')
    ).count()
    return f"REC-{today_str}-{count + 1:05d}"


def get_active_promos(produit_id, categorie):
    """Retourne le pourcentage de promo actif le plus élevé pour un produit."""
    today = date.today()
    promos = Promotion.query.filter(
        Promotion.date_debut <= today,
        Promotion.date_fin >= today,
        db.or_(
            Promotion.produit_id == produit_id,
            Promotion.categorie == categorie
        )
    ).all()
    if not promos:
        return 0.0
    return max(p.pourcentage for p in promos)


def log_audit(action, detail=None, ancienne_valeur=None, nouvelle_valeur=None):
    """Enregistre une entrée dans le journal d'audit."""
    try:
        ip = request.remote_addr if request else None
        entry = AuditLog(
            user_id=session.get('user_id'),
            action=action,
            detail=detail,
            ancienne_valeur=str(ancienne_valeur) if ancienne_valeur is not None else None,
            nouvelle_valeur=str(nouvelle_valeur) if nouvelle_valeur is not None else None,
            ip_address=ip,
        )
        db.session.add(entry)
        db.session.flush()
    except Exception as exc:
        app.logger.warning(f"log_audit failed for action={action}: {exc}")


def current_user():
    uid = session.get('user_id')
    if uid:
        return User.query.get(uid)
    return None


# Injecter les variables globales dans tous les templates
@app.context_processor
def inject_globals():
    params = None
    seuil = 5
    try:
        params = get_params()
        seuil = params.seuil_stock_bas or 5
    except Exception:
        pass
    return {
        'params': params,
        'current_user': current_user(),
        'format_montant': format_montant,
        'STOCK_BAS_SEUIL': seuil,
        'DEVISES': DEVISES,
        'now': datetime.utcnow(),
    }


# ──────────────────────────────────────────────────────────
# Authentification
# ──────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        mdp = request.form.get('mot_de_passe', '')
        try:
            user = User.query.filter_by(email=email).first()
            if user and user.actif and check_password_hash(user.mot_de_passe_hash, mdp):
                session.clear()
                session['user_id'] = user.id
                session['role'] = user.role
                session['nom'] = user.nom
                user.derniere_connexion = datetime.utcnow()
                log_audit('CONNEXION', f"Connexion réussie : {user.email}")
                db.session.commit()
                flash(f'Bienvenue, {user.nom} !', 'success')
                return redirect(url_for('dashboard'))
            else:
                log_audit('CONNEXION_ECHEC', f"Tentative échouée pour : {email}")
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                flash('Email ou mot de passe incorrect, ou compte désactivé.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Erreur lors de la connexion.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_audit('DECONNEXION', f"Déconnexion de {session.get('nom', '')}")
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('login'))


# ──────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    params = get_params()
    if session['role'] == 'admin':
        return render_template('dashboard.html', user=user, params=params)
    else:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ventes_jour = Vente.query.filter(
            Vente.agent_id == user.id,
            Vente.date >= today_start
        ).count()
        ca_jour = db.session.query(func.sum(Vente.total)).filter(
            Vente.agent_id == user.id,
            Vente.date >= today_start
        ).scalar() or 0
        return render_template('dashboard.html', user=user, params=params,
                               ventes_jour=ventes_jour, ca_jour=ca_jour)


# ──────────────────────────────────────────────────────────
# Profil
# ──────────────────────────────────────────────────────────
@app.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    user = current_user()
    if request.method == 'POST':
        try:
            file = request.files.get('photo')
            if file and file.filename:
                old_photo = user.photo_profil
                filename = save_image(file, prefix='profil', max_size=(300, 300))
                if filename:
                    user.photo_profil = filename
                    if old_photo:
                        delete_image(old_photo)
                    log_audit('MODIF_PROFIL', f"Changement de photo de profil de {user.nom}")
                    db.session.commit()
                    flash('Photo de profil mise à jour.', 'success')
                else:
                    flash('Image invalide ou format non autorisé (JPG, PNG, WEBP).', 'danger')
            else:
                flash('Aucun fichier sélectionné.', 'warning')
        except Exception:
            db.session.rollback()
            flash('Erreur lors de la mise à jour de la photo.', 'danger')
    return render_template('profil.html', user=user)


# ──────────────────────────────────────────────────────────
# Stock
# ──────────────────────────────────────────────────────────
@app.route('/stock')
@login_required
def stock():
    params = get_params()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    categorie = request.args.get('categorie', '').strip()
    devise_filtre = request.args.get('devise', '').strip()

    query = Produit.query
    if search:
        query = query.filter(Produit.nom.ilike(f'%{search}%'))
    if categorie:
        query = query.filter(Produit.categorie == categorie)
    if devise_filtre in DEVISES:
        query = query.filter(Produit.devise == devise_filtre)
    query = query.order_by(Produit.categorie, Produit.nom)

    produits = query.paginate(page=page, per_page=params.pagination or 20, error_out=False)
    categories = db.session.query(Produit.categorie).distinct().order_by(Produit.categorie).all()
    categories = [c[0] for c in categories]
    return render_template('stock.html', produits=produits, categories=categories,
                           search=search, categorie_filtre=categorie,
                           devise_filtre=devise_filtre)


@app.route('/produit/nouveau', methods=['GET', 'POST'])
@admin_required
def produit_nouveau():
    if request.method == 'POST':
        try:
            nom = request.form.get('nom', '').strip()
            categorie = request.form.get('categorie', '').strip()
            prix_str = request.form.get('prix', '0').strip()
            stock_str = request.form.get('stock', '0').strip()
            devise = request.form.get('devise', 'FC').strip()
            description = request.form.get('description', '').strip()

            if not nom or not categorie:
                flash('Le nom et la catégorie sont obligatoires.', 'danger')
                return redirect(request.url)
            if devise not in DEVISES:
                devise = 'FC'
            prix = float(prix_str)
            stock_qty = int(stock_str)
            if prix < 0 or stock_qty < 0:
                flash('Le prix et le stock ne peuvent pas être négatifs.', 'danger')
                return redirect(request.url)

            file = request.files.get('image')
            image_filename = save_image(file, prefix='prod', max_size=(400, 400)) if file and file.filename else None

            p = Produit(nom=nom, categorie=categorie, prix=prix, devise=devise,
                        stock=stock_qty, description=description, image=image_filename)
            db.session.add(p)
            db.session.flush()
            log_audit('AJOUT_PRODUIT', f"Produit ajouté : {nom}",
                      nouvelle_valeur=f"nom={nom}, cat={categorie}, prix={prix} {devise}, stock={stock_qty}")
            db.session.commit()
            flash(f'Produit "{nom}" ajouté avec succès.', 'success')
            return redirect(url_for('stock'))
        except ValueError:
            db.session.rollback()
            flash('Valeurs numériques invalides (prix ou stock).', 'danger')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"produit_nouveau: {e}")
            flash("Erreur lors de l'ajout du produit.", 'danger')
    categories = db.session.query(Produit.categorie).distinct().order_by(Produit.categorie).all()
    categories = [c[0] for c in categories]
    return render_template('produit_form.html', produit=None, categories=categories)


@app.route('/produit/<int:id>/modifier', methods=['GET', 'POST'])
@admin_required
def produit_modifier(id):
    produit = Produit.query.get_or_404(id)
    if request.method == 'POST':
        try:
            old_vals = f"nom={produit.nom}, prix={produit.prix} {produit.devise}, stock={produit.stock}"
            nom = request.form.get('nom', produit.nom).strip()
            cat = request.form.get('categorie', produit.categorie).strip()
            prix = float(request.form.get('prix', produit.prix))
            devise = request.form.get('devise', produit.devise).strip()
            stock_qty = int(request.form.get('stock', produit.stock))
            if prix < 0 or stock_qty < 0:
                flash('Le prix et le stock ne peuvent pas être négatifs.', 'danger')
                return redirect(request.url)
            if devise not in DEVISES:
                devise = produit.devise
            produit.nom = nom
            produit.categorie = cat
            produit.prix = prix
            produit.devise = devise
            produit.stock = stock_qty
            produit.description = request.form.get('description', produit.description or '').strip()
            file = request.files.get('image')
            if file and file.filename:
                new_img = save_image(file, prefix='prod', max_size=(400, 400))
                if new_img:
                    if produit.image:
                        delete_image(produit.image)
                    produit.image = new_img
                else:
                    flash('Image invalide ou format non autorisé — image non modifiée.', 'warning')
            new_vals = f"nom={produit.nom}, prix={produit.prix} {produit.devise}, stock={produit.stock}"
            log_audit('MODIF_PRODUIT', f"Produit modifié : {produit.nom}",
                      ancienne_valeur=old_vals, nouvelle_valeur=new_vals)
            db.session.commit()
            flash(f'Produit "{produit.nom}" mis à jour.', 'success')
            return redirect(url_for('stock'))
        except ValueError:
            db.session.rollback()
            flash('Valeurs numériques invalides.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Erreur lors de la mise à jour.', 'danger')
    categories = db.session.query(Produit.categorie).distinct().order_by(Produit.categorie).all()
    categories = [c[0] for c in categories]
    return render_template('produit_form.html', produit=produit, categories=categories)


@app.route('/produit/<int:id>/supprimer', methods=['POST'])
@admin_required
def produit_supprimer(id):
    produit = Produit.query.get_or_404(id)
    try:
        nom = produit.nom
        if produit.image:
            delete_image(produit.image)
        LigneVente.query.filter_by(produit_id=id).update({'produit_id': None})
        Promotion.query.filter_by(produit_id=id).delete()
        db.session.delete(produit)
        log_audit('SUPPR_PRODUIT', f"Produit supprimé : {nom}")
        db.session.commit()
        flash(f'Produit "{nom}" supprimé.', 'success')
    except Exception:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('stock'))


# ──────────────────────────────────────────────────────────
# Caisse
# ──────────────────────────────────────────────────────────
@app.route('/caisse')
@login_required
def caisse():
    params = get_params()
    produits = Produit.query.order_by(Produit.categorie, Produit.nom).all()
    promos_data = []
    for p in produits:
        pct = get_active_promos(p.id, p.categorie)
        # Prix affiché dans la devise d'origine du produit
        prix_avec_promo = round(p.prix * (1 - pct / 100), 2) if pct else p.prix
        # Prix converti dans la devise active de la caisse (pour le calcul du total)
        prix_converti = convertir(prix_avec_promo, p.devise, params.devise_active,
                                  params.taux_change_usd_fc)
        promos_data.append({
            'id': p.id,
            'nom': p.nom,
            'categorie': p.categorie,
            'prix': p.prix,                        # prix brut dans la devise produit
            'devise': p.devise,                    # devise du prix affiché
            'stock': p.stock,
            'promo_pct': pct,
            'prix_final': prix_avec_promo,         # prix après promo (devise produit)
            'prix_final_converti': prix_converti,  # prix converti dans la devise active caisse
        })
    return render_template('caisse.html',
                           produits_json=json.dumps(promos_data),
                           params=params)


@app.route('/caisse', methods=['POST'])
@login_required
@csrf.exempt   # JSON fetch — token envoyé via X-CSRFToken
def caisse_valider():
    # Vérification manuelle du token CSRF
    token = request.headers.get('X-CSRFToken', '')
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(token)
    except Exception:
        return jsonify({'error': 'Token CSRF invalide. Rechargez la page.'}), 400

    try:
        data = request.get_json()
        if not data or not data.get('lignes'):
            return jsonify({'error': 'Panier vide.'}), 400

        lignes_data = data['lignes']
        params = get_params()
        total = 0.0
        lignes_obj = []
        devises_utilisees = set()

        for item in lignes_data:
            produit = Produit.query.get(int(item['produit_id']))
            if not produit:
                return jsonify({'error': f"Produit introuvable (id={item['produit_id']})."}), 400
            qty = int(item['quantite'])
            if qty <= 0:
                return jsonify({'error': 'Quantité invalide.'}), 400
            if produit.stock < qty:
                return jsonify({
                    'error': f'Stock insuffisant pour "{produit.nom}" (disponible : {produit.stock}).'
                }), 400

            # Calcul du prix après promo dans la devise du produit
            pct = get_active_promos(produit.id, produit.categorie)
            prix_apres_promo = round(produit.prix * (1 - pct / 100), 4) if pct else produit.prix
            prix_original_promo = produit.prix if pct else None

            # Conversion vers la devise active de la caisse
            prix_converti = convertir(prix_apres_promo, produit.devise,
                                      params.devise_active, params.taux_change_usd_fc)
            prix_original_converti = (
                convertir(prix_original_promo, produit.devise,
                          params.devise_active, params.taux_change_usd_fc)
                if prix_original_promo else None
            )

            sous_total = round(prix_converti * qty, 4)
            total += sous_total
            devises_utilisees.add(produit.devise)

            lignes_obj.append(LigneVente(
                produit_id=produit.id,
                nom_produit=produit.nom,
                quantite=qty,
                prix_unitaire=prix_converti,            # dans la devise de la vente
                prix_original=prix_original_converti,   # dans la devise de la vente
                promo_pct=pct if pct else None,
                sous_total=sous_total,
                devise_produit=produit.devise,
                prix_unitaire_origine=prix_apres_promo, # dans la devise du produit
            ))
            produit.stock -= qty

        multi_devises = len(devises_utilisees) > 1 or (
            len(devises_utilisees) == 1 and
            list(devises_utilisees)[0] != params.devise_active
        )

        numero = generate_numero_recu()
        vente = Vente(
            agent_id=session['user_id'],
            total=round(total, 4),
            devise=params.devise_active,
            taux_change_utilise=params.taux_change_usd_fc,
            numero_recu=numero,
            multi_devises=multi_devises,
        )
        db.session.add(vente)
        db.session.flush()
        for l in lignes_obj:
            l.vente_id = vente.id
            db.session.add(l)

        log_audit('VENTE', f"Vente {numero} — Total {total:.4f} {params.devise_active}"
                  + (' [multi-devises]' if multi_devises else ''))
        db.session.commit()
        return jsonify({'success': True, 'recu_url': url_for('recu', id=vente.id)})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"caisse_valider: {e}")
        return jsonify({'error': f'Erreur lors de la validation : {str(e)}'}), 500


@app.route('/vente/<int:id>/recu')
@login_required
def recu(id):
    vente = Vente.query.get_or_404(id)
    if session['role'] != 'admin' and vente.agent_id != session['user_id']:
        abort(403)
    lignes = vente.lignes.all()
    params = get_params()
    agent = User.query.get(vente.agent_id)
    sous_total_brut = sum(
        (l.prix_original or l.prix_unitaire) * l.quantite for l in lignes
    )
    remise_total = sous_total_brut - vente.total
    return render_template('recu.html', vente=vente, lignes=lignes,
                           params=params, agent=agent,
                           sous_total_brut=sous_total_brut,
                           remise_total=remise_total)


# ──────────────────────────────────────────────────────────
# Historique
# ──────────────────────────────────────────────────────────
@app.route('/historique')
@login_required
def historique():
    params = get_params()
    page = request.args.get('page', 1, type=int)
    periode = request.args.get('periode', 'mois')
    agent_id_filtre = request.args.get('agent_id', type=int)

    now = datetime.utcnow()
    if periode == 'jour':
        debut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == 'semaine':
        debut = now - timedelta(days=now.weekday())
        debut = debut.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    query = Vente.query.filter(Vente.date >= debut)
    if session['role'] == 'admin':
        if agent_id_filtre:
            query = query.filter(Vente.agent_id == agent_id_filtre)
        agents = User.query.filter_by(role='agent').order_by(User.nom).all()
    else:
        query = query.filter(Vente.agent_id == session['user_id'])
        agents = []

    ventes = query.order_by(Vente.date.desc()).paginate(
        page=page, per_page=params.pagination or 20, error_out=False)
    return render_template('historique.html', ventes=ventes, periode=periode,
                           agents=agents, agent_id_filtre=agent_id_filtre)


# ──────────────────────────────────────────────────────────
# Admin — Agents
# ──────────────────────────────────────────────────────────
@app.route('/agents')
@admin_required
def agents():
    params = get_params()
    page = request.args.get('page', 1, type=int)
    agents_pag = User.query.filter_by(role='agent').order_by(User.nom)\
        .paginate(page=page, per_page=params.pagination or 20, error_out=False)
    return render_template('agents.html', agents=agents_pag)


@app.route('/agents/nouveau', methods=['GET', 'POST'])
@admin_required
def agent_nouveau():
    if request.method == 'POST':
        try:
            nom = request.form.get('nom', '').strip()
            email = request.form.get('email', '').strip().lower()
            mdp = request.form.get('mot_de_passe', '')
            if not nom or not email or not mdp:
                flash('Tous les champs obligatoires doivent être remplis.', 'danger')
                return render_template('agent_form.html', agent=None)
            if len(mdp) < 6:
                flash('Le mot de passe doit contenir au moins 6 caractères.', 'danger')
                return render_template('agent_form.html', agent=None)
            if User.query.filter_by(email=email).first():
                flash('Cet email est déjà utilisé.', 'danger')
                return render_template('agent_form.html', agent=None)
            file = request.files.get('photo')
            photo = save_image(file, prefix='agent', max_size=(300, 300)) if file and file.filename else None
            user = User(nom=nom, email=email,
                        mot_de_passe_hash=generate_password_hash(mdp),
                        role='agent', actif=True, photo_profil=photo)
            db.session.add(user)
            db.session.flush()
            log_audit('CREATION_AGENT', f"Compte agent créé : {email}",
                      nouvelle_valeur=f"nom={nom}, email={email}")
            db.session.commit()
            flash(f'Agent "{nom}" créé avec succès.', 'success')
            return redirect(url_for('agents'))
        except Exception:
            db.session.rollback()
            flash("Erreur lors de la création de l'agent.", 'danger')
    return render_template('agent_form.html', agent=None)


@app.route('/agents/<int:id>/modifier', methods=['GET', 'POST'])
@admin_required
def agent_modifier(id):
    agent = User.query.get_or_404(id)
    if request.method == 'POST':
        try:
            old_vals = f"nom={agent.nom}, email={agent.email}, actif={agent.actif}"
            agent.nom = request.form.get('nom', agent.nom).strip()
            new_email = request.form.get('email', agent.email).strip().lower()
            if new_email != agent.email and User.query.filter_by(email=new_email).first():
                flash('Cet email est déjà utilisé par un autre compte.', 'danger')
                return render_template('agent_form.html', agent=agent)
            agent.email = new_email
            agent.actif = request.form.get('actif') == 'on'
            mdp = request.form.get('mot_de_passe', '').strip()
            if mdp:
                if len(mdp) < 6:
                    flash('Le mot de passe doit contenir au moins 6 caractères.', 'danger')
                    return render_template('agent_form.html', agent=agent)
                agent.mot_de_passe_hash = generate_password_hash(mdp)
                log_audit('MODIF_MDP_AGENT', f"Mot de passe modifié pour : {agent.email}")
            file = request.files.get('photo')
            if file and file.filename:
                new_photo = save_image(file, prefix='agent', max_size=(300, 300))
                if new_photo:
                    if agent.photo_profil:
                        delete_image(agent.photo_profil)
                    agent.photo_profil = new_photo
            new_vals = f"nom={agent.nom}, email={agent.email}, actif={agent.actif}"
            log_audit('MODIF_AGENT', f"Compte agent modifié : {agent.email}",
                      ancienne_valeur=old_vals, nouvelle_valeur=new_vals)
            db.session.commit()
            flash(f'Agent "{agent.nom}" mis à jour.', 'success')
            return redirect(url_for('agents'))
        except Exception:
            db.session.rollback()
            flash("Erreur lors de la mise à jour de l'agent.", 'danger')
    return render_template('agent_form.html', agent=agent)


@app.route('/agents/<int:id>/supprimer', methods=['POST'])
@admin_required
def agent_supprimer(id):
    agent = User.query.get_or_404(id)
    try:
        nom = agent.nom
        email = agent.email
        if agent.photo_profil:
            delete_image(agent.photo_profil)
        Vente.query.filter_by(agent_id=id).update({'agent_id': session['user_id']})
        log_audit('SUPPR_AGENT', f"Compte agent supprimé : {email}",
                  ancienne_valeur=f"nom={nom}, email={email}")
        db.session.delete(agent)
        db.session.commit()
        flash(f'Agent "{nom}" supprimé.', 'success')
    except Exception:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('agents'))


# ──────────────────────────────────────────────────────────
# Admin — Statistiques
# ──────────────────────────────────────────────────────────
@app.route('/statistiques')
@admin_required
def statistiques():
    return render_template('statistiques.html')


@app.route('/api/dashboard-stats')
@admin_required
def api_dashboard_stats():
    try:
        params = get_params()
        seuil = params.seuil_stock_bas or 5
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        ca_jour = db.session.query(func.sum(Vente.total)).filter(
            Vente.date >= today_start).scalar() or 0
        nb_ventes_jour = Vente.query.filter(Vente.date >= today_start).count()
        stock_bas_count = Produit.query.filter(Produit.stock < seuil,
                                               Produit.stock >= 0).count()
        agents_actifs = User.query.filter_by(role='agent', actif=True).count()

        ventes_7j = []
        for i in range(6, -1, -1):
            jour = (now - timedelta(days=i)).date()
            debut_jour = datetime.combine(jour, datetime.min.time())
            fin_jour = datetime.combine(jour, datetime.max.time())
            total_j = db.session.query(func.sum(Vente.total)).filter(
                Vente.date.between(debut_jour, fin_jour)).scalar() or 0
            ventes_7j.append({'date': jour.strftime('%d/%m'), 'montant': round(total_j, 2)})

        il_y_a_30j = now - timedelta(days=30)
        top_agents_q = db.session.query(
            User.id, User.nom, User.photo_profil,
            func.sum(Vente.total).label('total_ventes')
        ).join(Vente, Vente.agent_id == User.id)\
         .filter(Vente.date >= il_y_a_30j)\
         .group_by(User.id, User.nom, User.photo_profil)\
         .order_by(func.sum(Vente.total).desc())\
         .limit(5).all()
        top_agents = [{'nom': r.nom, 'photo': r.photo_profil,
                       'montant': round(r.total_ventes, 2)} for r in top_agents_q]

        stock_bas = Produit.query.filter(
            Produit.stock < seuil, Produit.stock >= 0
        ).order_by(Produit.stock).limit(10).all()
        stock_bas_list = [{'id': p.id, 'nom': p.nom, 'stock': p.stock,
                           'devise': p.devise} for p in stock_bas]

        cat_ventes_q = db.session.query(
            Produit.categorie,
            func.sum(LigneVente.sous_total).label('total')
        ).join(LigneVente, LigneVente.produit_id == Produit.id)\
         .join(Vente, Vente.id == LigneVente.vente_id)\
         .filter(Vente.date >= il_y_a_30j)\
         .group_by(Produit.categorie).all()
        ventes_cat = [{'categorie': r.categorie, 'montant': round(r.total, 2)}
                      for r in cat_ventes_q]

        return jsonify({
            'ca_jour': round(ca_jour, 2),
            'nb_ventes_jour': nb_ventes_jour,
            'stock_bas_count': stock_bas_count,
            'agents_actifs': agents_actifs,
            'ventes_7j': ventes_7j,
            'top_agents': top_agents,
            'stock_bas': stock_bas_list,
            'ventes_cat': ventes_cat,
            'devise': params.devise_active,
            'taux': params.taux_change_usd_fc,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────
# Admin — Promotions
# ──────────────────────────────────────────────────────────
@app.route('/promotions', methods=['GET', 'POST'])
@admin_required
def promotions():
    if request.method == 'POST':
        try:
            produit_id = request.form.get('produit_id') or None
            categorie = request.form.get('categorie', '').strip() or None
            pct = float(request.form.get('pourcentage', 0))
            d_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d').date()
            d_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d').date()

            if not produit_id and not categorie:
                flash('Sélectionnez un produit ou une catégorie.', 'danger')
            elif d_fin < d_debut:
                flash('La date de fin doit être après la date de début.', 'danger')
            elif pct <= 0 or pct >= 100:
                flash('Le pourcentage doit être entre 1 et 99.', 'danger')
            else:
                promo = Promotion(
                    produit_id=int(produit_id) if produit_id else None,
                    categorie=categorie,
                    pourcentage=pct,
                    date_debut=d_debut,
                    date_fin=d_fin,
                )
                db.session.add(promo)
                desc = f"Promotion {pct}% du {d_debut} au {d_fin}"
                if produit_id:
                    p = Produit.query.get(int(produit_id))
                    desc += f" sur {p.nom if p else produit_id}"
                else:
                    desc += f" sur catégorie {categorie}"
                log_audit('CREATION_PROMO', desc, nouvelle_valeur=f"{pct}%")
                db.session.commit()
                flash('Promotion créée avec succès.', 'success')
                return redirect(url_for('promotions'))
        except ValueError:
            db.session.rollback()
            flash('Valeurs invalides.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Erreur lors de la création.', 'danger')

    today = date.today()
    toutes = Promotion.query.order_by(Promotion.date_fin.desc()).all()
    actives = [p for p in toutes if p.date_debut <= today <= p.date_fin]
    expirees = [p for p in toutes if p.date_fin < today]
    a_venir = [p for p in toutes if p.date_debut > today]

    produits = Produit.query.order_by(Produit.categorie, Produit.nom).all()
    categories = db.session.query(Produit.categorie).distinct().order_by(Produit.categorie).all()
    categories = [c[0] for c in categories]
    return render_template('promotions.html', actives=actives, expirees=expirees,
                           a_venir=a_venir, produits=produits, categories=categories)


@app.route('/promotions/<int:id>/supprimer', methods=['POST'])
@admin_required
def promotion_supprimer(id):
    promo = Promotion.query.get_or_404(id)
    try:
        desc = f"Promotion {promo.pourcentage}% (id={id})"
        log_audit('SUPPR_PROMO', f"Promotion supprimée : {desc}")
        db.session.delete(promo)
        db.session.commit()
        flash('Promotion supprimée.', 'success')
    except Exception:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('promotions'))


# ──────────────────────────────────────────────────────────
# Admin — Paramètres
# ──────────────────────────────────────────────────────────
@app.route('/parametres', methods=['GET', 'POST'])
@admin_required
def parametres():
    params = get_params()
    if request.method == 'POST':
        try:
            old_snap = (params.nom_magasin, params.devise_active,
                        params.taux_change_usd_fc, params.adresse,
                        params.telephone, params.site_web,
                        params.message_recu, params.seuil_stock_bas, params.pagination)

            params.nom_magasin = request.form.get('nom_magasin', params.nom_magasin).strip() or params.nom_magasin
            params.devise_active = request.form.get('devise_active', params.devise_active)
            if params.devise_active not in DEVISES:
                params.devise_active = 'FC'

            taux_raw = request.form.get('taux_change', str(params.taux_change_usd_fc)).strip()
            taux_val = float(taux_raw)
            if taux_val <= 0:
                raise ValueError("Le taux doit être positif.")
            params.taux_change_usd_fc = taux_val

            params.adresse = request.form.get('adresse', '').strip() or None
            params.telephone = request.form.get('telephone', '').strip() or None
            params.site_web = request.form.get('site_web', '').strip() or None
            params.message_recu = request.form.get('message_recu', '').strip() or 'Merci pour votre achat !'
            seuil_raw = request.form.get('seuil_stock_bas', '5').strip()
            pagi_raw = request.form.get('pagination', '20').strip()
            params.seuil_stock_bas = max(1, int(seuil_raw)) if seuil_raw.isdigit() else 5
            params.pagination = max(5, min(100, int(pagi_raw))) if pagi_raw.isdigit() else 20

            file = request.files.get('logo')
            if file and file.filename:
                new_logo = save_image(file, prefix='logo', max_size=(600, 300))
                if new_logo:
                    if params.logo:
                        delete_image(params.logo)
                    params.logo = new_logo
                else:
                    flash('Image logo invalide ou format non autorisé.', 'warning')

            new_snap = (params.nom_magasin, params.devise_active,
                        params.taux_change_usd_fc, params.adresse,
                        params.telephone, params.site_web,
                        params.message_recu, params.seuil_stock_bas, params.pagination)
            if old_snap != new_snap:
                log_audit('MODIF_PARAMETRES',
                          f"Paramètres mis à jour par {session.get('nom', '')}",
                          ancienne_valeur=str(old_snap),
                          nouvelle_valeur=str(new_snap))
            db.session.commit()
            flash('Paramètres mis à jour.', 'success')
            return redirect(url_for('parametres'))
        except ValueError as e:
            db.session.rollback()
            flash(f'Valeur invalide : {e}', 'danger')
        except Exception:
            db.session.rollback()
            flash('Erreur lors de la mise à jour.', 'danger')
    return render_template('parametres.html', params=params)


# ──────────────────────────────────────────────────────────
# Admin — Journal d'audit
# ──────────────────────────────────────────────────────────
@app.route('/audit')
@admin_required
def audit():
    params = get_params()
    page = request.args.get('page', 1, type=int)
    user_filtre = request.args.get('user_id', type=int)
    action_filtre = request.args.get('action', '').strip()
    periode = request.args.get('periode', '30j')

    now = datetime.utcnow()
    if periode == 'aujourd_hui':
        debut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == '7j':
        debut = now - timedelta(days=7)
    elif periode == '30j':
        debut = now - timedelta(days=30)
    else:
        debut = None

    query = AuditLog.query
    if debut:
        query = query.filter(AuditLog.date_heure >= debut)
    if user_filtre:
        query = query.filter(AuditLog.user_id == user_filtre)
    if action_filtre:
        query = query.filter(AuditLog.action.ilike(f'%{action_filtre}%'))

    logs = query.order_by(AuditLog.date_heure.desc())\
        .paginate(page=page, per_page=params.pagination or 20, error_out=False)
    users = User.query.order_by(User.nom).all()
    actions = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    actions = [a[0] for a in actions]
    return render_template('audit.html', logs=logs, users=users, actions=actions,
                           user_filtre=user_filtre, action_filtre=action_filtre,
                           periode=periode)


@app.route('/audit/export.csv')
@admin_required
def audit_export_csv():
    user_filtre = request.args.get('user_id', type=int)
    action_filtre = request.args.get('action', '').strip()
    periode = request.args.get('periode', '30j')

    now = datetime.utcnow()
    if periode == 'aujourd_hui':
        debut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == '7j':
        debut = now - timedelta(days=7)
    elif periode == '30j':
        debut = now - timedelta(days=30)
    else:
        debut = None

    query = AuditLog.query
    if debut:
        query = query.filter(AuditLog.date_heure >= debut)
    if user_filtre:
        query = query.filter(AuditLog.user_id == user_filtre)
    if action_filtre:
        query = query.filter(AuditLog.action.ilike(f'%{action_filtre}%'))
    logs = query.order_by(AuditLog.date_heure.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date/Heure', 'Utilisateur', 'Action', 'Détail',
                     'Ancienne valeur', 'Nouvelle valeur', 'IP'])
    for log in logs:
        writer.writerow([
            log.date_heure.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.nom if log.user else 'Système',
            log.action,
            log.detail or '',
            log.ancienne_valeur or '',
            log.nouvelle_valeur or '',
            log.ip_address or '',
        ])

    filename = f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/historique/export.csv')
@admin_required
def historique_export_csv():
    periode = request.args.get('periode', 'mois')
    agent_id_filtre = request.args.get('agent_id', type=int)

    now = datetime.utcnow()
    if periode == 'jour':
        debut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periode == 'semaine':
        debut = now - timedelta(days=now.weekday())
        debut = debut.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    query = Vente.query.filter(Vente.date >= debut)
    if agent_id_filtre:
        query = query.filter(Vente.agent_id == agent_id_filtre)
    ventes = query.order_by(Vente.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['N° Reçu', 'Date', 'Agent', 'Total', 'Devise', 'Taux 1$=FC', 'Multi-devises', 'Articles'])
    for v in ventes:
        agent = User.query.get(v.agent_id)
        lignes = v.lignes.all()
        articles = '; '.join(
            f"{l.nom_produit} x{l.quantite}"
            + (f" [{l.devise_produit}]" if l.devise_produit else "")
            for l in lignes
        )
        writer.writerow([
            v.numero_recu,
            v.date.strftime('%Y-%m-%d %H:%M'),
            agent.nom if agent else 'N/A',
            f"{v.total:.4f}",
            v.devise,
            f"{v.taux_change_utilise:.0f}",
            'Oui' if v.multi_devises else 'Non',
            articles,
        ])

    filename = f"ventes_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ──────────────────────────────────────────────────────────
# Fichiers uploadés
# ──────────────────────────────────────────────────────────
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    filename = os.path.basename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ──────────────────────────────────────────────────────────
# Gestionnaires d'erreurs
# ──────────────────────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(429)
def too_many_requests(e):
    flash('Trop de tentatives. Veuillez patienter avant de réessayer.', 'danger')
    return redirect(url_for('login'))


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('errors/500.html'), 500


# ──────────────────────────────────────────────────────────
# Point d'entrée
# ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        run_migrations()
    app.run(debug=True)
