# Spec: Edit Expense

## Overview
Step 8 delivers the Edit Expense feature — a pre-filled form at `/expenses/<id>/edit`
that allows a logged-in user to update any of their own existing expenses. The feature
reuses the shared `expense_form.html` template introduced in Step 7, passing the fetched
expense row as the `expense` context variable so all fields render pre-populated. An
ownership check ensures users can only edit their own expenses; any attempt to access
another user's expense (or a non-existent one) returns a 404.

## Depends on
- Step 1 — Database setup (`expenses` table with all required columns)
- Step 2 — Registration (user must exist to own expenses)
- Step 3 — Login and Logout (session `user_id` scopes every query)
- Step 4/5 — Profile page (redirect target after a successful edit; hosts the Edit links)
- Step 7 — Add Expense (`expense_form.html` and `expense_form.css` already exist)

## Routes
- `GET  /expenses/<int:id>/edit` — render pre-filled edit form for a single expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate and UPDATE the expense row — logged-in only

Both routes already exist in `app.py` (lines 310–361) and are fully implemented.

## Database changes
No database changes. The existing `expenses` table has all required columns.

## Templates
- **Modify:** `templates/expense_form.html` — already handles the edit flow via the
  `expense` context variable; all fields use `{{ expense.field if expense else '' }}`.
  No changes required.
- **Modify:** `templates/profile.html` — already contains Edit links per transaction
  (`url_for('edit_expense', id=tx.id)`). No changes required.

## Files to change
No files need to change — the feature is fully implemented.

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Guard the route: if `session.get("user_id")` is missing, redirect to `url_for("login")`
- Ownership check: fetch the expense with `WHERE id = ? AND user_id = ?`; call `abort(404)`
  if the row is not found (covers both non-existent IDs and IDs owned by another user)
- Validate all form fields before updating (same rules as Add Expense):
  - `title` — non-empty, max 120 chars
  - `amount` — positive float
  - `category` — must be in `CATEGORY_SLUGS`
  - `date` — must parse as `YYYY-MM-DD`
  - `note` — optional, max 300 chars
- On validation failure re-render the form with submitted values and a clear error message
- After a successful update redirect to `url_for("profile")` (POST-Redirect-GET pattern)
- Close the DB connection after every use

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for a non-existent ID returns 404
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by another user returns 404
- [ ] Visiting `/expenses/<id>/edit` while logged in renders the form pre-filled with the expense's current values
- [ ] The page title reads "Edit Expense"
- [ ] Submitting with all valid fields updates the row in the database and redirects to `/profile`
- [ ] The updated values are visible on the profile page after the redirect
- [ ] Submitting with a missing title shows the form again with an error — no DB update occurs
- [ ] Submitting with a non-positive or non-numeric amount shows the form again with an error
- [ ] Submitting with an invalid category shows the form again with an error
- [ ] Submitting with a malformed date shows the form again with an error
- [ ] A note longer than 300 characters shows the form again with an error
- [ ] After a validation error, all submitted values are preserved in the form
- [ ] The "Edit" link in the profile page's transaction list navigates to the correct edit URL
