# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv venv
source venv/Scripts/activate   # Windows bash
pip install -r requirements.txt

# Run
python app.py                  # Starts dev server at http://localhost:5001

# Test
pytest                         # Run all tests
pytest tests/test_foo.py       # Run a single test file
```

## Architecture

Flask app with Jinja2 templates and SQLite. No frontend build step — plain HTML/CSS/JS.

**Entry point**: `app.py` — defines all routes and starts the server on port 5001 with debug mode.

**Database**: `database/db.py` centralizes all DB access. The three functions to implement/use are:
- `get_db()` — returns a SQLite connection with `row_factory` set and foreign keys enabled
- `init_db()` — creates tables (`CREATE TABLE IF NOT EXISTS`)
- `seed_db()` — inserts sample data

The DB file (`expense_tracker.db`) is gitignored and generated at runtime.

**Templates**: Jinja2 with inheritance — all pages extend `templates/base.html` via `{% extends %}` / `{% block %}`. The base provides the navbar, footer, and layout.

**Routes** (stub placeholders exist for all of these in `app.py`):
| Route | Purpose |
|---|---|
| `GET /` | Landing page |
| `GET /register` | Registration form |
| `GET /login` | Login form |
| `GET /logout` | Logout (Step 3) |
| `GET /profile` | User profile (Step 4) |
| `GET /expenses/add` | Add expense (Step 7) |
| `GET /expenses/<id>/edit` | Edit expense (Step 8) |
| `GET /expenses/<id>/delete` | Delete expense (Step 9) |

**Styling**: Custom CSS with design tokens in `static/css/style.css` (global) and `static/css/landing.css` (landing page only). Key colors: accent green `#1a472a`, accent orange `#c17f24`. Fonts: DM Serif Display (headings), DM Sans (body) via Google Fonts.

## Development Notes

The project is built incrementally across 9 numbered steps (comments in `app.py` mark each step). Steps 1–2 cover database setup and auth; Steps 3–9 add expense CRUD. Routes exist as stubs — implement handlers in order.

Tests use `pytest-flask`. When writing tests, use the `app` fixture from `pytest-flask` conventions.
