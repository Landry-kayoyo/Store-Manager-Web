---
name: Flask Store migration SQLite
description: Comment ajouter de nouvelles colonnes à une BDD SQLite existante
---

SQLite ne supporte pas `ALTER TABLE ... ADD COLUMN` avec contraintes complexes, et Flask-SQLAlchemy `db.create_all()` ne modifie pas les tables existantes.

Approche utilisée : dans `init_db.py`, fonction `migrate_db()` qui :
1. Inspecte les colonnes existantes via `sqlalchemy.inspect(engine)`
2. Pour chaque colonne manquante, exécute `ALTER TABLE xxx ADD COLUMN yyy TYPE DEFAULT val`
3. Wrap dans un try/except pour être idempotent

**Why:** Pas de Flask-Migrate dans le projet pour garder les dépendances minimales.

**How to apply:** À chaque ajout de colonne dans models.py, ajouter la migration correspondante dans la liste `new_cols` de `init_db.py::migrate_db()`. Lancer `python init_db.py` pour appliquer.
