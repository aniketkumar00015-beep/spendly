# Spec: Add Expense

## Overview
Step 7 delivers the Add Expense feature — a dedicated form page at `/expenses/add`
where a logged-in user can record a new expense with a title, amount, category, date,
and optional note. The backend route, template, and shared form CSS were scaffolded
earlier (spec 05); this step finalises the feature by resolving outstanding CSS
variable violations, verifying end-to-end behaviour, and ensuring the UI matches the
Spendly design system conventions.

## Depends on
- Step 1 — Database setup (`expenses` table with all required columns)
- Step 2 — Registration (user must exist to own expenses)
- Step 3 — Login and Logout (session `user_id` scopes every query)
- Step 4/5 — Profile page (the redirect target after a successful add)

## Routes
- `GET  /expenses/add` — render blank add-expense form — logged-in only
- `POST /expenses/add` — validate and insert new expense row — logged-in only

Both routes already exist in `app.py` and are fully implemented. No new routes needed.

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `title`, `amount`, `category`, `date`, `note`, `created_at`.

## Templates
- **Modify:** `templates/expense_form.html` — already exists; verify it renders
  correctly for the add flow (`expense=None`, `form_title="Add Expense"`)

## Files to change
- `static/css/expense_form.css` — replace two hardcoded hex values with CSS
  variables:
  - Line 37: `border: 1px solid #f5c6c2` → `border: 1px solid var(--danger-border)`
  - Line 220: `border-color: #f5c6c2` → `border-color: var(--danger-border)`
- `static/css/style.css` — add `--danger-border` token if it does not already exist

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (not relevant here, but never expose the `password` column)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Guard the route: if `session.get("user_id")` is missing, redirect to `url_for("login")`
- Validate all form fields before inserting:
  - `title` — non-empty string, max 120 chars
  - `amount` — positive float, reject non-numeric input
  - `category` — must be one of the known `CATEGORY_SLUGS`
  - `date` — must parse as `YYYY-MM-DD`
  - `note` — optional, max 300 chars
- On validation failure re-render the form with submitted values and a clear error message
- After successful add redirect to `url_for("profile")` (POST-Redirect-GET pattern)
- Close the DB connection after every use

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a blank form with the title "Add Expense"
- [ ] Submitting the form with all valid fields inserts a new row in `expenses` and redirects to `/profile`
- [ ] The new expense appears in the profile page's recent transactions with the correct values
- [ ] Submitting with a missing title shows the form again with an error — no DB write occurs
- [ ] Submitting with a non-positive or non-numeric amount shows the form again with an error
- [ ] Submitting with an invalid category shows the form again with an error
- [ ] Submitting with a malformed date shows the form again with an error
- [ ] A note longer than 300 characters shows the form again with an error
- [ ] After a validation error, all previously entered values are preserved in the form
- [ ] No hardcoded hex values remain in `expense_form.css`
