# Spec: Date Filter for Profile Page

## Overview
This feature adds a date-range filter to the profile page so users can focus on expenses within a specific period. Without filtering, the profile always shows all-time stats, which becomes noisy as the expense history grows. By passing `from` and `to` query parameters on `GET /profile`, the route scopes its SQL query, recomputes all summary stats (total spent, transaction count, top category, category breakdown), and re-renders the full transactions list for that window. Quick-select presets (This Month, Last Month, Last 3 Months, All Time) let users jump to common ranges without typing dates manually.

## Depends on
- Step 04 — Profile page design (template structure)
- Step 05 — Backend routes for profile page (profile route and expense queries)

## Routes
No new routes. The existing `GET /profile` route is extended to accept optional query parameters:
- `from` — start date in `YYYY-MM-DD` format (inclusive)
- `to` — end date in `YYYY-MM-DD` format (inclusive)

## Database changes
No database changes. The existing `expenses` table already has a `date TEXT` column. Filtering is done by adding a `WHERE date BETWEEN ? AND ?` clause to the existing query.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats section with two date inputs (`from`, `to`) and an Apply button
  - Add four quick-select preset buttons: "This Month", "Last Month", "Last 3 Months", "All Time"
  - Show an active-filter badge when a filter is applied (e.g. "Showing: 01 Apr 2026 – 13 May 2026")
  - The transactions list should show ALL filtered transactions (not capped at 6) when a filter is active; keep the 6-item cap only when no filter is set
  - Preserve filter values in the form inputs on re-render

## Files to change
- `app.py` — modify `profile()` route to read `from`/`to` query params, validate them, apply them to the SQL query, and pass filter state to the template

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate date strings into SQL
- Passwords hashed with werkzeug (no change here, but maintain existing auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date validation in Python: reject malformed dates with `datetime.strptime`; silently ignore invalid params and fall back to no filter
- The filter is applied server-side — no JS required for the core behaviour
- Quick-preset buttons may use vanilla JS to populate the date inputs and submit the form (no fetch/AJAX — just form submit)
- When `from` is missing but `to` is provided (or vice versa), treat as no filter (both must be present for filtering to apply)
- `from` must be ≤ `to`; if violated, fall back to no filter and render an inline error message

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time stats (unchanged baseline behaviour)
- [ ] Visiting `/profile?from=2026-04-01&to=2026-04-30` scopes total spent, transaction count, top category, and category breakdown to April 2026 only
- [ ] The date inputs in the filter bar are pre-filled with the active `from`/`to` values on re-render
- [ ] An active-filter badge is visible when a date range is applied; it is absent when viewing all-time
- [ ] Clicking "This Month" populates the date fields with the first and last day of the current month and submits the form
- [ ] Clicking "Last Month" populates the fields with the first and last day of the previous month and submits
- [ ] Clicking "Last 3 Months" sets `from` to 3 calendar months ago (first day) and `to` to today
- [ ] Clicking "All Time" clears the filter and redirects to `/profile` with no params
- [ ] When `from` > `to`, the page re-renders with an inline error and no filter applied
- [ ] Malformed date strings in query params (e.g. `from=abc`) are silently ignored and the page renders unfiltered
- [ ] When a filter is active, the transactions list shows all matching expenses (not limited to 6)
- [ ] When no filter is active, the transactions list is capped at 6 (existing behaviour)
