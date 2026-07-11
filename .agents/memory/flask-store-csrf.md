---
name: Flask Store CSRF
description: Configuration CSRF Flask-WTF et gestion de l'endpoint JSON caisse
---

- `CSRFProtect(app)` activé globalement — tous les formulaires doivent avoir `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- `<meta name="csrf-token" content="{{ csrf_token() }}">` dans base.html pour les fetch() JS
- L'endpoint `/caisse` POST est décoré `@csrf.exempt` car il reçoit du JSON, mais fait une vérification manuelle via `validate_csrf(request.headers.get('X-CSRFToken'))`.
- caisse.js lit le token depuis `meta[name="csrf-token"]` ou la variable globale `CSRF_TOKEN` et l'envoie en header `X-CSRFToken`.

**Why:** Flask-WTF ne parse pas le corps JSON pour y chercher le token CSRF ; il faut passer par le header ou exempter + valider manuellement.

**How to apply:** Pour tout nouvel endpoint AJAX JSON : soit exempt + validate_csrf manuel, soit envoyer le token en header X-CSRFToken depuis le JS.
