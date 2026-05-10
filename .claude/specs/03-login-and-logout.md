# Spec: Login and Logout

## Overview
This step implements session-based authentication for Spendly. Visiting `/login` shows a form; submitting it looks up the user by email, verifies the password hash, and — on success — stores the user in the Flask session before redirecting to the landing page. Visiting `/logout` clears the session and redirects to `/login`. Together these two routes gate all future authenticated features and complete the core auth cycle started in Step 2.

## Depends on
- Step 1 — Database setup (`users` table and `get_db()` must exist)
- Step 2 — Registration (users must exist in the DB with hashed passwords)

## Routes
- `GET /login` — render the login form — public
- `POST /login` — validate credentials, start session, redirect — public
- `GET /logout` — clear session, redirect to `/login` — public (but only meaningful when logged in)

## Database changes
No database changes. The `users` table already contains all required columns (id, username, email, password).

## Templates
- **Create:** `templates/login.html` — login form extending `base.html` with email and password fields
- **Modify:** `templates/base.html` — swap the Register/Login nav links for a Logout link when the user is logged in (`session.user_id` is set)

## Files to change
- `app.py` — upgrade `/login` to handle GET and POST; implement `/logout` to clear session and redirect; import `check_password_hash` from `werkzeug.security`
- `templates/base.html` — conditionally show Login/Register vs Logout in the navbar based on `session`

## Files to create
- `templates/login.html`

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Verify passwords with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values in templates or stylesheets
- All templates extend `base.html`
- Look up users by **email** (not username) on login — email is the unique login identifier
- On invalid credentials (user not found or wrong password) give a single generic error: "Invalid email or password." — do not distinguish which field failed
- On success, store `session["user_id"]` and `session["username"]`, then redirect to `url_for("landing")`
- `/logout` must call `session.clear()` (not just pop individual keys), then redirect to `url_for("login")`
- Do not require authentication for `/logout` — a stale session or direct GET should still clear cleanly and redirect

## Definition of done
- [ ] `GET /login` returns a 200 with a form containing email and password fields
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/`
- [ ] Submitting a non-existent email shows "Invalid email or password." and stays on `/login`
- [ ] Submitting a correct email with the wrong password shows "Invalid email or password." and stays on `/login`
- [ ] Submitting with any empty field shows a validation error and stays on `/login`
- [ ] After login, the navbar shows a Logout link instead of Register/Login
- [ ] `GET /logout` clears the session and redirects to `/login`
- [ ] After logout, the navbar shows Register and Login links again
- [ ] Visiting `/logout` with no active session redirects cleanly to `/login` without error
