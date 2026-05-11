# Spec: Backend Routes For Profile Page

## Overview
This step implements the three expense CRUD backend routes that power the profile page's
live data: add, edit, and delete. The profile page already renders expense totals,
category breakdowns, and recent transactions — but with no way to create or modify
expenses, that data can only be seeded manually. Completing these routes makes the
profile page fully interactive and closes the loop on the core Spendly feature set.

## Depends on
- Step 1 — Database setup (`expenses` table with all required columns)
- Step 2 — Registration (user must exist to own expenses)
- Step 3 — Login and Logout (session `user_id` scopes every query)
- Step 4 — Profile page design (the page that displays the result of these routes)

## Routes
- `GET  /expenses/add`        — render blank add-expense form — logged-in only
- `POST /expenses/add`        — validate and insert new expense row — logged-in only
- `GET  /expenses/<id>/edit`  — render pre-filled edit form for expense owned by session user — logged-in only
- `POST /expenses/<id>/edit`  — validate and update expense row — logged-in only
- `GET  /expenses/<id>/delete`— delete expense row (ownership verified) and redirect to profile — logged-in only

## Database changes
No new tables or columns. All required columns already exist on the `expenses` table:
`id`, `user_id`, `title`, `amount`, `category`, `date`, `note`, `created_at`.

## Templates
- **Create:** `templates/expense_form.html` — shared add/edit form extending `base.html`;
  receives `form_title`, `action_url`, and optional `expense` dict for pre-fill
- **Modify:** `templates/profile.html` — add "Add expense" button/link pointing to
  `url_for('add_expense')`; add edit and delete links on each row in the recent
  transactions list

## Files to change
- `app.py` — replace the three stub route handlers (`add_expense`, `edit_expense`,
  `delete_expense`) with real implementations
- `templates/profile.html` — add "Add expense" CTA and edit/delete controls per row

## Files to create
- `templates/expense_form.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (not relevant here, but never expose the `password` column)
- Use CSS variables — never hardcode hex values in templates or new CSS
- All templates extend `base.html`
- Guard every route: if `session.get("user_id")` is missing, redirect to `url_for("login")`
- Ownership check on edit and delete: fetch the expense by `id` AND `user_id = session["user_id"]`;
  return 404 if not found (prevents one user editing another's data)
- Validate all form fields before inserting/updating:
  - `title` — non-empty string, max 120 chars
  - `amount` — positive float, reject non-numeric input
  - `category` — must be one of the known `CATEGORY_SLUGS`
  - `date` — must parse as `YYYY-MM-DD`
  - `note` — optional, max 300 chars
- On validation failure re-render the form with the submitted values and a clear error message
- After successful add/edit/delete redirect to `url_for("profile")` (POST-Redirect-GET)
- Close the DB connection after every use
- The delete route requires no confirmation template — a direct GET is sufficient at this stage
- Reuse the existing `_category_slug` and `_format_date` helpers already in `app.py`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Submitting the add form with valid data creates a new row in `expenses` and redirects to `/profile`
- [ ] The new expense appears in the profile page's recent transactions and updates the totals
- [ ] Submitting the add form with missing/invalid fields re-renders the form with an error (no DB write)
- [ ] Visiting `/expenses/<id>/edit` shows the form pre-filled with the existing expense values
- [ ] Submitting the edit form with valid data updates the row and redirects to `/profile`
- [ ] A logged-in user cannot edit or delete another user's expense (returns 404)
- [ ] Visiting `/expenses/<id>/delete` removes the row and redirects to `/profile`
- [ ] After deletion the expense no longer appears on the profile page
- [ ] All three routes redirect to `/login` when the session has no `user_id`
