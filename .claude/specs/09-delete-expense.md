# Spec: Delete Expense

## Overview
Step 9 delivers the Delete Expense feature, allowing a logged-in user to permanently
remove one of their own expenses. The `GET /expenses/<id>/delete` route is already
implemented in `app.py` (lines 372–393) and performs a safe ownership-scoped DELETE.
The profile template also already renders a Delete link per transaction. This step
upgrades the confirmation UX from a bare browser `confirm()` dialog to a dedicated
confirmation page — making the flow accessible, consistently styled, and harder to
trigger accidentally.

## Depends on
- Step 1 — Database setup (`expenses` table must exist)
- Step 2 — Registration (user must exist to own expenses)
- Step 3 — Login and Logout (session `user_id` scopes every query)
- Step 4/5 — Profile page (the delete link lives in the transaction list)
- Step 7 — Add Expense (establishes expenses to delete)

## Routes
- `GET  /expenses/<int:id>/delete` — show confirmation page for the expense — logged-in only
- `POST /expenses/<int:id>/delete` — execute the DELETE and redirect — logged-in only

The GET route currently skips confirmation and deletes immediately. This step splits it
into a two-step flow: GET renders `delete_confirm.html`; POST performs the deletion.

## Database changes
No database changes. The `expenses` table already supports deletion via parameterised query.

## Templates
- **Create:** `templates/delete_confirm.html` — confirmation page showing the expense
  title, amount, and category with a "Yes, delete" submit button and a "Cancel" link back
  to `/profile`.
- **Modify:** `templates/profile.html` — remove the inline `onclick="return confirm(...)"` from
  the Delete link (the dedicated page now handles confirmation).

## Files to change
- `app.py` — refactor `delete_expense` to:
  - `GET`: fetch the expense (ownership check), render `delete_confirm.html`
  - `POST`: fetch again (re-verify ownership), delete, redirect to `url_for("profile")`
- `templates/profile.html` — strip the `onclick` attribute from the Delete `<a>` tag

## Files to create
- `templates/delete_confirm.html` — dedicated confirmation page

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (not relevant here, but keep as convention)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Guard both GET and POST: if `session.get("user_id")` is missing, redirect to `url_for("login")`
- Ownership check on both GET and POST: `WHERE id = ? AND user_id = ?`; call `abort(404)` if not found
- The POST route must re-fetch the expense before deleting — do not trust hidden form fields for the ID
- After a successful DELETE redirect to `url_for("profile")` (POST-Redirect-GET pattern)
- The confirmation page must show: expense title, amount (formatted to 2 decimal places), and category
- "Cancel" must be a plain `<a href="{{ url_for('profile') }}">` link, not a form submit
- Close the DB connection after every use

## Definition of done
- [ ] Clicking Delete on the profile page navigates to `/expenses/<id>/delete` — no deletion yet
- [ ] The confirmation page shows the expense's title, amount, and category
- [ ] The confirmation page has a "Yes, delete" button and a "Cancel" link
- [ ] Clicking "Cancel" returns the user to `/profile` with no changes
- [ ] Clicking "Yes, delete" submits a POST, deletes the expense, and redirects to `/profile`
- [ ] The deleted expense no longer appears in the profile transaction list after the redirect
- [ ] Visiting `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/delete` for a non-existent ID returns 404
- [ ] Visiting `/expenses/<id>/delete` for an expense owned by another user returns 404
- [ ] POSTing directly to `/expenses/<id>/delete` for another user's expense returns 404
