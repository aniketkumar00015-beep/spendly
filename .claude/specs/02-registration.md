# Spec: Registration

## Overview
This step implements user account creation for Spendly. Visiting `/register` shows a form; submitting it validates the input, hashes the password, inserts a new row into the `users` table, starts a session, and redirects the user to the dashboard (or login page). It is the entry point for all authenticated features and must be complete before login, profile, or any expense work can begin.

## Depends on
- Step 1 — Database setup (`users` table must exist, `get_db()` must work)

## Routes
- `GET /register` — render the registration form — public
- `POST /register` — validate input, create user, start session, redirect — public

## Database changes
No database changes. The `users` table (id, username, email, password, created_at) already exists from Step 1.

## Templates
- **Create:** `templates/register.html` — registration form extending `base.html`
- **Modify:** `templates/base.html` — add nav link to `/register` if not already present

## Files to change
- `app.py` — add `secret_key`, import session/redirect/flash/request, implement GET and POST handlers for `/register`
- `database/db.py` — add `create_user(username, email, password_hash)` helper (optional but recommended)
- `templates/base.html` — ensure nav links to Register and Login are present

## Files to create
- `templates/register.html`

## New dependencies
No new dependencies. `werkzeug.security` is already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` before insertion
- Use CSS variables — never hardcode hex values in templates or stylesheets
- All templates extend `base.html`
- Set `app.secret_key` (read from env var `SECRET_KEY`, fallback to a dev default)
- Validate all fields server-side: username, email, and password must be non-empty; email must contain `@`; username and email must be unique (catch `IntegrityError`)
- On validation failure, re-render the form with a flash error message — do not redirect
- On success, store `user_id` and `username` in `session`, then redirect to `/` (or a dashboard route when available)
- Never store the plain-text password anywhere

## Definition of done
- [ ] `GET /register` returns a 200 with a form containing username, email, password, and confirm-password fields
- [ ] Submitting the form with valid unique data creates a row in `users` and redirects away from `/register`
- [ ] The stored password column is a werkzeug hash, not plain text (verify with `sqlite3 expense_tracker.db "SELECT password FROM users LIMIT 1"`)
- [ ] Submitting with a duplicate email shows a flash error and stays on `/register`
- [ ] Submitting with a duplicate username shows a flash error and stays on `/register`
- [ ] Submitting with an empty field shows a flash error and stays on `/register`
- [ ] Submitting with mismatched passwords shows a flash error and stays on `/register`
- [ ] After successful registration, `session['user_id']` is set (visible in debug toolbar or a test route)
- [ ] The register page is reachable from the navbar
