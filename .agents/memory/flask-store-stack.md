---
name: Flask Store stack
description: Stack technique et structure du projet flask-store/
---

- Flask 3.0 + Flask-SQLAlchemy + SQLite dans flask-store/ (standalone, pas dans le monorepo pnpm)
- Flask-WTF (CSRF), Flask-Limiter (rate limit login), Pillow (images), Werkzeug
- Deux rôles : admin (full access) et agent (caisse + historique propre)
- Auth manuelle via session Flask, pas Flask-Login
- Palette : vert forêt #1A3A2A + or #C89B3C + parchemin #F3F0EA
- Compte admin par défaut : admin@magasin.com / admin123

**Why:** User demandait Flask explicitement pour déploiement PythonAnywhere.

**How to apply:** Toujours faire `python init_db.py` après modification de models.py (migration douce via ALTER TABLE dans init_db.py).
