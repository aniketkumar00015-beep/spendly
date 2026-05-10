# Spec: Profile Page Design

## Overview
This step implements the `/profile` page — the first authenticated-only screen in Spendly. It shows the logged-in user's account details (username, email, member-since date) in a clean, card-based layout that matches the existing visual language (DM Serif Display headings, deep forest green accent, amber highlights). It also serves as the foundation for future profile features (edit details, change password, delete account) by establishing the route guard pattern and the page structure that later steps will build on.

## Depends on
- Step 1 — Database setup (`users` table with `id`, `username`, `email`, `created_at`)
- Step 2 — Registration (account creation populates `users`)
- Step 3 — Login and Logout (session must hold `user_id` so the page can identify the viewer)

## Routes
- `GET /profile` — render the logged-in user's profile page — logged-in only (redirect to `/login` if no `session["user_id"]`)

## Database changes
No database changes. All required columns (`id`, `username`, `email`, `created_at`) already exist on the `users` table in `database/db.py`.

## Templates
- **Create:** `templates/profile.html` — profile page extending `base.html`, showing user details in a card layout
- **Modify:** `templates/base.html` — add a "Profile" link to the navbar's logged-in branch (between brand and Sign out)

## Files to change
- `app.py` — replace the `/profile` stub with a real handler that requires login, fetches the user row by `session["user_id"]`, and renders `profile.html`
- `templates/base.html` — add Profile nav link inside the `{% if session.get("user_id") %}` block

## Files to create
- `templates/profile.html`
- `static/css/profile.css`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (no password handling here, but never expose the `password` column to the template)
- Use CSS variables — never hardcode hex values in `profile.css` or the template
- All templates extend `base.html`
- Guard the route: if `session.get("user_id")` is missing, redirect to `url_for("login")` — do not render the page
- Fetch only the columns needed (`username`, `email`, `created_at`) — never `SELECT *` and never pass the password hash to the template
- Close the DB connection after use
- Format `created_at` as a human-readable date in the template (e.g. "Joined May 2026") — do not show raw timestamps
- Follow the design system in `.claude/skills/frontend-design/SKILL.md`: card layout with `--shadow-md` and `--radius-md`, 8px spacing grid, DM Serif Display for the page title, Lucide icons for the user/email/calendar fields
- Use the green accent (`--color-accent`) for the page heading or avatar; amber (`--color-amber`) for at most one highlight (e.g. member-since badge)
- Mobile-first responsive with a single breakpoint at 768px

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Visiting `/profile` while logged in returns 200 and renders the profile page
- [ ] The page shows the logged-in user's username and email (matching the values from the `users` table)
- [ ] The page shows a "member since" or "joined" line derived from `created_at`, formatted as a human-readable date
- [ ] The password hash is never present in the rendered HTML (verify by viewing source)
- [ ] The navbar includes a "Profile" link when logged in, and clicking it loads `/profile`
- [ ] The page extends `base.html` and uses only CSS variables (no hardcoded hex values in `profile.css` or the template)
- [ ] Layout uses card styling with shadow and rounded corners consistent with other pages
- [ ] Page is readable and well-laid-out at both 375px (mobile) and 1280px (desktop) widths
