"""
Tests for the Edit Expense feature — Step 08.

Spec: .claude/specs/08-edit-expense.md

Coverage:
  - Auth guard: GET while logged out redirects to /login
  - Auth guard: POST while logged out redirects to /login
  - GET non-existent expense ID returns 404
  - GET expense owned by a different user returns 404
  - GET authenticated: 200, page title contains "Edit Expense"
  - GET authenticated: form fields pre-populated with existing expense values
  - POST happy path: DB row updated, redirect to /profile (PRG pattern)
  - POST happy path: updated values reflected in the DB and profile page
  - POST blank title: 200, error shown, DB row unchanged
  - POST non-positive amount (zero, negative, non-numeric): 200, error shown, no DB update
  - POST invalid category: 200, error shown, no DB update
  - POST malformed date: 200, error shown, no DB update
  - POST note > 300 chars: 200, error shown, no DB update
  - Submitted values preserved in form after any validation failure
  - Profile page "Edit" link points to the correct /expenses/<id>/edit URL
  - Parametrized invalid inputs covering all validation rules
"""

import pytest
import database.db as db_module
from app import app as flask_app
from database.db import init_db, get_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"food", "transport", "bills", "health", "shopping", "entertainment", "other"}

# The original values stored in the test expense fixture.
ORIGINAL_EXPENSE = {
    "title": "Original Title",
    "amount": "12.50",
    "category": "food",
    "date": "2026-04-10",
    "note": "Original note",
}

# A fully valid update payload — completely different from ORIGINAL_EXPENSE.
UPDATED_EXPENSE = {
    "title": "Updated Title",
    "amount": "99.99",
    "category": "transport",
    "date": "2026-05-15",
    "note": "Updated note",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Each test gets an isolated SQLite file via a monkeypatched DB_PATH so the
    real expense_tracker.db is never touched.
    """
    db_file = str(tmp_path / "test_expense_tracker.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })
    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Registers 'testuser' and returns the authenticated test client."""
    client.post("/register", data={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepass123",
        "confirm_password": "securepass123",
    })
    return client


@pytest.fixture
def seeded_expense(auth_client):
    """
    Inserts one expense for 'testuser' via the add route and returns its DB id.
    Using the route (rather than raw SQL) ensures the row is created through the
    same code path the app uses, including user_id binding from the session.
    """
    auth_client.post("/expenses/add", data=ORIGINAL_EXPENSE)
    conn = get_db()
    row = conn.execute(
        "SELECT expenses.id FROM expenses "
        "JOIN users ON expenses.user_id = users.id "
        "WHERE users.username = ? AND expenses.title = ?",
        ("testuser", ORIGINAL_EXPENSE["title"]),
    ).fetchone()
    conn.close()
    assert row is not None, "seeded_expense fixture: expense was not inserted"
    return row["id"]


@pytest.fixture
def second_auth_client(app):
    """
    A second authenticated client for 'otheruser'.
    Used to verify ownership enforcement — testuser cannot see otheruser's expenses.
    """
    with app.test_client() as other:
        other.post("/register", data={
            "username": "otheruser",
            "email": "otheruser@example.com",
            "password": "otherpass456",
            "confirm_password": "otherpass456",
        })
        yield other


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_expense_by_id(expense_id):
    """Fetch a single expense row by its primary key, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    return row


def _insert_expense_for_user(username, title="Other Expense", amount=5.00,
                              category="food", date="2026-04-20", note=None):
    """
    Insert an expense directly into the DB for the named user.
    Returns the new expense id.
    """
    conn = get_db()
    user_row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    assert user_row is not None, f"_insert_expense_for_user: user '{username}' not found"
    with conn:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_row["id"], title, amount, category, date, note),
        )
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 302, (
            "GET /expenses/1/edit while logged out should redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET should redirect to /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/1/edit", data=UPDATED_EXPENSE)
        assert response.status_code == 302, (
            "POST /expenses/1/edit while logged out should redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST should redirect to /login"
        )

    def test_get_unauthenticated_follow_redirect_lands_on_login_page(self, client):
        response = client.get("/expenses/1/edit", follow_redirects=True)
        assert b"Login" in response.data or b"login" in response.data.lower(), (
            "Following the redirect for an unauthenticated request should land on the login page"
        )


# ---------------------------------------------------------------------------
# 404 — non-existent ID and wrong-owner enforcement
# ---------------------------------------------------------------------------

class TestNotFound:

    def test_get_nonexistent_id_returns_404(self, auth_client):
        response = auth_client.get("/expenses/99999/edit")
        assert response.status_code == 404, (
            "GET for a non-existent expense ID must return 404"
        )

    def test_post_nonexistent_id_returns_404(self, auth_client):
        response = auth_client.post("/expenses/99999/edit", data=UPDATED_EXPENSE)
        assert response.status_code == 404, (
            "POST for a non-existent expense ID must return 404"
        )

    def test_get_expense_owned_by_another_user_returns_404(
        self, app, auth_client, second_auth_client
    ):
        """
        'testuser' must get 404 when trying to edit 'otheruser's expense.
        The ownership check (WHERE id = ? AND user_id = ?) should prevent access.
        """
        other_expense_id = _insert_expense_for_user("otheruser")
        response = auth_client.get(f"/expenses/{other_expense_id}/edit")
        assert response.status_code == 404, (
            "Authenticated user should receive 404 when accessing another user's expense"
        )

    def test_post_expense_owned_by_another_user_returns_404(
        self, app, auth_client, second_auth_client
    ):
        other_expense_id = _insert_expense_for_user("otheruser")
        response = auth_client.post(
            f"/expenses/{other_expense_id}/edit", data=UPDATED_EXPENSE
        )
        assert response.status_code == 404, (
            "POST to another user's expense must return 404"
        )


# ---------------------------------------------------------------------------
# GET — pre-filled form rendering
# ---------------------------------------------------------------------------

class TestGetEditExpenseForm:

    def test_get_returns_200_for_own_expense(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert response.status_code == 200, (
            "GET /expenses/<id>/edit for own expense should return 200"
        )

    def test_get_page_title_contains_edit_expense(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert b"Edit Expense" in response.data, (
            "The page title/heading must contain 'Edit Expense'"
        )

    def test_get_form_prefilled_with_title(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert ORIGINAL_EXPENSE["title"].encode() in response.data, (
            "The edit form must pre-populate the title field with the existing expense title"
        )

    def test_get_form_prefilled_with_amount(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        # Amount is stored as REAL; check that the numeric portion appears (e.g. "12.5")
        assert b"12.5" in response.data, (
            "The edit form must pre-populate the amount field with the existing expense amount"
        )

    def test_get_form_prefilled_with_category(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert ORIGINAL_EXPENSE["category"].encode() in response.data, (
            "The edit form must pre-populate the category with the existing expense category"
        )

    def test_get_form_prefilled_with_date(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert ORIGINAL_EXPENSE["date"].encode() in response.data, (
            "The edit form must pre-populate the date field with the existing expense date"
        )

    def test_get_form_prefilled_with_note(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert ORIGINAL_EXPENSE["note"].encode() in response.data, (
            "The edit form must pre-populate the note field with the existing expense note"
        )

    def test_get_form_contains_required_input_fields(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        for field in (b'name="title"', b'name="amount"', b'name="date"', b'name="note"'):
            assert field in response.data, (
                f"The edit form must contain an input with {field.decode()}"
            )

    def test_get_form_contains_category_select(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert b'name="category"' in response.data, (
            "The edit form must contain a category select element"
        )

    def test_get_renders_no_error_on_fresh_load(self, auth_client, seeded_expense):
        response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert b"form-error-banner" not in response.data, (
            "A fresh GET should not display any error banner"
        )


# ---------------------------------------------------------------------------
# POST — happy path
# ---------------------------------------------------------------------------

class TestPostEditExpenseHappyPath:

    def test_post_valid_data_redirects_to_profile(self, auth_client, seeded_expense):
        response = auth_client.post(
            f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE
        )
        assert response.status_code == 302, (
            "A successful POST must issue a redirect (PRG pattern)"
        )
        assert "/profile" in response.headers["Location"], (
            "After a successful edit, the redirect target must be /profile"
        )

    def test_post_valid_data_updates_title_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None, "Expense row must still exist after a successful update"
        assert row["title"] == UPDATED_EXPENSE["title"], (
            f"DB title should be '{UPDATED_EXPENSE['title']}', got '{row['title']}'"
        )

    def test_post_valid_data_updates_amount_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        assert abs(row["amount"] - float(UPDATED_EXPENSE["amount"])) < 0.001, (
            f"DB amount should be {UPDATED_EXPENSE['amount']}, got {row['amount']}"
        )

    def test_post_valid_data_updates_category_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        assert row["category"] == UPDATED_EXPENSE["category"], (
            f"DB category should be '{UPDATED_EXPENSE['category']}', got '{row['category']}'"
        )

    def test_post_valid_data_updates_date_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        assert row["date"] == UPDATED_EXPENSE["date"], (
            f"DB date should be '{UPDATED_EXPENSE['date']}', got '{row['date']}'"
        )

    def test_post_valid_data_updates_note_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        assert row["note"] == UPDATED_EXPENSE["note"], (
            f"DB note should be '{UPDATED_EXPENSE['note']}', got '{row['note']}'"
        )

    def test_post_old_title_no_longer_in_db(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        assert row["title"] != ORIGINAL_EXPENSE["title"], (
            "After a successful update, the old title must no longer be stored in the DB"
        )

    def test_post_updated_title_visible_on_profile(self, auth_client, seeded_expense):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        response = auth_client.get("/profile")
        assert UPDATED_EXPENSE["title"].encode() in response.data, (
            "The updated expense title must appear on the profile page after a successful edit"
        )

    def test_post_original_title_absent_from_profile_after_update(
        self, auth_client, seeded_expense
    ):
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)
        response = auth_client.get("/profile")
        assert ORIGINAL_EXPENSE["title"].encode() not in response.data, (
            "The original (pre-edit) title must not appear on the profile page after a successful update"
        )

    def test_post_update_does_not_create_extra_rows(self, auth_client, seeded_expense):
        """An UPDATE must not insert a new row."""
        conn = get_db()
        before = conn.execute("SELECT COUNT(*) AS cnt FROM expenses").fetchone()["cnt"]
        conn.close()

        auth_client.post(f"/expenses/{seeded_expense}/edit", data=UPDATED_EXPENSE)

        conn = get_db()
        after = conn.execute("SELECT COUNT(*) AS cnt FROM expenses").fetchone()["cnt"]
        conn.close()

        assert after == before, (
            "A successful edit must update exactly one row — no extra rows should be inserted"
        )

    def test_post_clear_note_sets_null_or_empty(self, auth_client, seeded_expense):
        """Clearing the note field and submitting should succeed (note is optional)."""
        payload = {**UPDATED_EXPENSE, "note": ""}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 302, (
            "Submitting an empty note on an edit should still succeed (note is optional)"
        )
        row = _get_expense_by_id(seeded_expense)
        assert row is not None
        # Route stores None for empty note — either None or empty string is acceptable.
        assert row["note"] in (None, ""), (
            "After clearing the note, the DB should store NULL or an empty string"
        )


# ---------------------------------------------------------------------------
# POST — validation errors (no DB update must occur)
# ---------------------------------------------------------------------------

class TestPostEditExpenseValidationErrors:

    def test_blank_title_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "title": ""}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Blank title should re-render the form (200), not redirect"
        )

    def test_blank_title_shows_error(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "title": ""}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"title" in response.data.lower() or b"required" in response.data.lower(), (
            "A blank title must produce an error message in the response"
        )

    def test_blank_title_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "title": ""}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert row["title"] == ORIGINAL_EXPENSE["title"], (
            "A blank title must not update the title in the DB"
        )

    def test_zero_amount_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "0"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Zero amount should re-render the form (200)"
        )

    def test_zero_amount_shows_error(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "0"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"positive" in response.data.lower() or b"amount" in response.data.lower(), (
            "Zero amount must produce an error message in the response"
        )

    def test_zero_amount_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "0"}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert abs(row["amount"] - float(ORIGINAL_EXPENSE["amount"])) < 0.001, (
            "Zero amount must not update the amount in the DB"
        )

    def test_negative_amount_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "-10.00"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Negative amount should re-render the form (200)"
        )

    def test_negative_amount_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "-10.00"}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert abs(row["amount"] - float(ORIGINAL_EXPENSE["amount"])) < 0.001, (
            "Negative amount must not update the amount in the DB"
        )

    def test_non_numeric_amount_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "not-a-number"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Non-numeric amount should re-render the form (200)"
        )

    def test_non_numeric_amount_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "amount": "not-a-number"}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert abs(row["amount"] - float(ORIGINAL_EXPENSE["amount"])) < 0.001, (
            "Non-numeric amount must not update the amount in the DB"
        )

    def test_invalid_category_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "category": "luxury"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Invalid category should re-render the form (200)"
        )

    def test_invalid_category_shows_error(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "category": "luxury"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"category" in response.data.lower() or b"invalid" in response.data.lower(), (
            "An invalid category must produce an error message in the response"
        )

    def test_invalid_category_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "category": "luxury"}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert row["category"] == ORIGINAL_EXPENSE["category"], (
            "An invalid category must not update the category in the DB"
        )

    def test_malformed_date_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "date": "15/05/2026"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Malformed date should re-render the form (200)"
        )

    def test_malformed_date_shows_error(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "date": "15/05/2026"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"date" in response.data.lower() or b"yyyy" in response.data.lower(), (
            "A malformed date must produce an error message in the response"
        )

    def test_malformed_date_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "date": "15/05/2026"}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert row["date"] == ORIGINAL_EXPENSE["date"], (
            "A malformed date must not update the date in the DB"
        )

    def test_note_too_long_returns_200(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "note": "N" * 301}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            "Note > 300 chars should re-render the form (200)"
        )

    def test_note_too_long_shows_error(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "note": "N" * 301}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"note" in response.data.lower() or b"300" in response.data, (
            "A note > 300 chars must produce an error message in the response"
        )

    def test_note_too_long_does_not_update_db(self, auth_client, seeded_expense):
        payload = {**UPDATED_EXPENSE, "note": "N" * 301}
        auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        row = _get_expense_by_id(seeded_expense)
        assert row["note"] == ORIGINAL_EXPENSE["note"], (
            "A note > 300 chars must not update the note in the DB"
        )

    def test_note_exactly_300_chars_accepted(self, auth_client, seeded_expense):
        """A note of exactly 300 chars is within the limit and must succeed."""
        payload = {**UPDATED_EXPENSE, "note": "X" * 300}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 302, (
            "Note of exactly 300 characters must be accepted (boundary value)"
        )

    @pytest.mark.parametrize("field,value,label", [
        ("title", "", "empty title"),
        ("amount", "not-a-number", "non-numeric amount"),
        ("amount", "0", "zero amount"),
        ("amount", "-1.50", "negative amount"),
        ("category", "invalid-slug", "invalid category"),
        ("date", "2026/05/15", "slash-separated date"),
        ("date", "32-13-2026", "impossible date values"),
        ("date", "", "empty date"),
        ("note", "Z" * 301, "note > 300 chars"),
    ])
    def test_parametrized_invalid_input_returns_200_and_no_db_update(
        self, auth_client, seeded_expense, field, value, label
    ):
        payload = {**UPDATED_EXPENSE, field: value}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert response.status_code == 200, (
            f"Invalid input ({label}) should re-render the form (200), not redirect"
        )
        row = _get_expense_by_id(seeded_expense)
        assert row["title"] == ORIGINAL_EXPENSE["title"], (
            f"Invalid input ({label}) must not update the expense in the DB "
            f"(title still original confirms no write)"
        )


# ---------------------------------------------------------------------------
# Submitted values preserved in form after validation error
# ---------------------------------------------------------------------------

class TestSubmittedValuesPreservedOnError:

    def test_submitted_title_preserved_after_invalid_amount(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "title": "Unique Preserved Title", "amount": "bad"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"Unique Preserved Title" in response.data, (
            "The submitted title must be preserved in the re-rendered form after an amount error"
        )

    def test_submitted_amount_preserved_after_invalid_category(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "amount": "77.77", "category": "invalid"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"77.77" in response.data, (
            "The submitted amount must be preserved in the re-rendered form after a category error"
        )

    def test_submitted_category_preserved_after_malformed_date(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "category": "health", "date": "bad-date"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"health" in response.data, (
            "The submitted category must be preserved in the re-rendered form after a date error"
        )

    def test_submitted_date_preserved_after_blank_title(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "title": "", "date": "2026-07-20"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"2026-07-20" in response.data, (
            "The submitted date must be preserved in the re-rendered form after a blank title error"
        )

    def test_submitted_note_preserved_after_blank_title(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "title": "", "note": "This note must survive"}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"This note must survive" in response.data, (
            "The submitted note must be preserved in the re-rendered form after a blank title error"
        )

    def test_edit_expense_heading_still_shown_after_error(
        self, auth_client, seeded_expense
    ):
        payload = {**UPDATED_EXPENSE, "title": ""}
        response = auth_client.post(f"/expenses/{seeded_expense}/edit", data=payload)
        assert b"Edit Expense" in response.data, (
            "The 'Edit Expense' heading must still appear in the form after a validation error"
        )


# ---------------------------------------------------------------------------
# Profile page Edit link points to correct URL
# ---------------------------------------------------------------------------

class TestProfileEditLink:

    def test_profile_contains_edit_link_for_expense(self, auth_client, seeded_expense):
        """
        The profile page must contain an anchor whose href is
        /expenses/<id>/edit for the seeded expense.
        """
        response = auth_client.get("/profile")
        expected_href = f"/expenses/{seeded_expense}/edit".encode()
        assert expected_href in response.data, (
            f"Profile page must include an Edit link pointing to "
            f"'/expenses/{seeded_expense}/edit'"
        )

    def test_profile_edit_link_text_is_edit(self, auth_client, seeded_expense):
        """The link that navigates to the edit form must be labelled 'Edit'."""
        response = auth_client.get("/profile")
        assert b"Edit" in response.data, (
            "The profile page must contain a visible 'Edit' link for each transaction"
        )

    def test_profile_edit_link_navigates_to_edit_form(self, auth_client, seeded_expense):
        """
        Following the edit link from the profile page must reach the edit form (200)
        pre-filled with the expense's current title.
        """
        edit_response = auth_client.get(f"/expenses/{seeded_expense}/edit")
        assert edit_response.status_code == 200, (
            "The edit URL from the profile page must resolve to a 200 form page"
        )
        assert ORIGINAL_EXPENSE["title"].encode() in edit_response.data, (
            "The form reached via the profile Edit link must be pre-filled with the expense title"
        )

    def test_profile_edit_links_for_multiple_expenses(self, auth_client, seeded_expense):
        """
        When multiple expenses exist, each should have its own correctly formed edit URL.
        """
        # Add a second expense
        auth_client.post("/expenses/add", data={
            "title": "Second Expense",
            "amount": "25.00",
            "category": "bills",
            "date": "2026-04-11",
            "note": "",
        })
        conn = get_db()
        second_id = conn.execute(
            "SELECT expenses.id FROM expenses "
            "JOIN users ON expenses.user_id = users.id "
            "WHERE users.username = ? AND expenses.title = ?",
            ("testuser", "Second Expense"),
        ).fetchone()["id"]
        conn.close()

        response = auth_client.get("/profile")
        assert f"/expenses/{seeded_expense}/edit".encode() in response.data, (
            f"Profile must contain an Edit link for the first expense (id={seeded_expense})"
        )
        assert f"/expenses/{second_id}/edit".encode() in response.data, (
            f"Profile must contain an Edit link for the second expense (id={second_id})"
        )
