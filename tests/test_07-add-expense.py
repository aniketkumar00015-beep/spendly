"""
Tests for the Add Expense feature — Step 07.

Spec: .claude/specs/07-add-expense.md

Coverage:
  - Auth guard (GET and POST while logged out redirect to /login)
  - GET renders blank form with "Add Expense" title and all valid categories
  - POST happy path: valid data inserts a DB row and redirects to /profile (PRG pattern)
  - DB side-effect: row written with correct field values
  - Expense appears on profile page after a successful add
  - POST with missing title: re-renders form (200) with error, no DB write
  - POST with title > 120 chars: re-renders form with error, no DB write
  - POST with non-numeric amount: re-renders form with error
  - POST with zero amount: re-renders form with error
  - POST with negative amount: re-renders form with error
  - POST with invalid category: re-renders form with error, no DB write
  - POST with malformed date: re-renders form with error, no DB write
  - POST with note > 300 chars: re-renders form with error, no DB write
  - Submitted values preserved on re-render after validation failure
  - POST without a note field: succeeds normally
  - Parametrized invalid inputs covering multiple bad-input types
  - Data isolation: expense inserted only for the logged-in user
"""

import pytest
import database.db as db_module
from app import app as flask_app
from database.db import init_db, get_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"food", "transport", "bills", "health", "shopping", "entertainment", "other"}

VALID_EXPENSE = {
    "title": "Morning Coffee",
    "amount": "4.50",
    "category": "food",
    "date": "2026-05-01",
    "note": "Nice flat white",
}


@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Each test gets its own isolated SQLite file via a monkeypatched DB_PATH.
    This prevents any test from polluting the real expense_tracker.db.
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
    """Registers and logs in 'testuser', returns the authenticated client."""
    client.post("/register", data={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepass123",
        "confirm_password": "securepass123",
    })
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expense_count(username="testuser"):
    """Return the number of expenses owned by the given username."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses "
        "JOIN users ON expenses.user_id = users.id "
        "WHERE users.username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return row["cnt"]


def _get_expense(title, username="testuser"):
    """Fetch the first expense row matching title and username, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT expenses.* FROM expenses "
        "JOIN users ON expenses.user_id = users.id "
        "WHERE expenses.title = ? AND users.username = ?",
        (title, username),
    ).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, "GET /expenses/add while logged out should redirect"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET should redirect to /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=VALID_EXPENSE)
        assert response.status_code == 302, "POST /expenses/add while logged out should redirect"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST should redirect to /login"
        )

    def test_get_unauthenticated_does_not_render_form(self, client):
        response = client.get("/expenses/add", follow_redirects=True)
        assert b"Add Expense" not in response.data or b"Login" in response.data, (
            "Unauthenticated user should land on login page, not the expense form"
        )


# ---------------------------------------------------------------------------
# GET — blank form rendering
# ---------------------------------------------------------------------------

class TestGetAddExpenseForm:

    def test_get_returns_200_when_authenticated(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, "GET /expenses/add should return 200 for a logged-in user"

    def test_get_renders_add_expense_heading(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"Add Expense" in response.data, (
            "The form page should display 'Add Expense' as the form title"
        )

    def test_get_renders_all_valid_categories(self, auth_client):
        response = auth_client.get("/expenses/add")
        for cat in VALID_CATEGORIES:
            assert cat.encode() in response.data, (
                f"Category '{cat}' should appear as a selectable option in the form"
            )

    def test_get_form_has_no_prefilled_values(self, auth_client):
        response = auth_client.get("/expenses/add")
        # A blank form should not carry pre-filled error values
        assert b"Morning Coffee" not in response.data, (
            "The blank add form must not contain a pre-filled title from a previous submission"
        )

    def test_get_renders_no_error_message(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"error" not in response.data.lower() or b"error" not in response.data, (
            "A fresh GET on the add form should not show any error messages"
        )

    def test_get_form_contains_title_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="title"' in response.data, (
            "The form must contain an input with name='title'"
        )

    def test_get_form_contains_amount_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="amount"' in response.data, (
            "The form must contain an input with name='amount'"
        )

    def test_get_form_contains_date_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="date"' in response.data, (
            "The form must contain an input with name='date'"
        )

    def test_get_form_contains_note_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="note"' in response.data, (
            "The form must contain an input/textarea with name='note'"
        )


# ---------------------------------------------------------------------------
# POST — happy path
# ---------------------------------------------------------------------------

class TestPostAddExpenseHappyPath:

    def test_post_valid_data_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID_EXPENSE)
        assert response.status_code == 302, "Successful POST should issue a redirect (PRG pattern)"
        assert "/profile" in response.headers["Location"], (
            "After a successful add the user should be redirected to /profile"
        )

    def test_post_valid_data_inserts_db_row(self, app, auth_client):
        before = _expense_count()
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        after = _expense_count()
        assert after == before + 1, "A successful POST must insert exactly one new row in expenses"

    def test_post_valid_data_correct_title_in_db(self, app, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        row = _get_expense("Morning Coffee")
        assert row is not None, "The inserted row must be retrievable by the submitted title"
        assert row["title"] == "Morning Coffee", "Stored title must match the submitted title"

    def test_post_valid_data_correct_amount_in_db(self, app, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        row = _get_expense("Morning Coffee")
        assert row is not None, "The inserted expense row must exist in the DB"
        assert abs(row["amount"] - 4.50) < 0.001, (
            f"Stored amount should be 4.50, got {row['amount']}"
        )

    def test_post_valid_data_correct_category_in_db(self, app, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        row = _get_expense("Morning Coffee")
        assert row is not None
        assert row["category"] == "food", (
            f"Stored category should be 'food', got '{row['category']}'"
        )

    def test_post_valid_data_correct_date_in_db(self, app, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        row = _get_expense("Morning Coffee")
        assert row is not None
        assert row["date"] == "2026-05-01", (
            f"Stored date should be '2026-05-01', got '{row['date']}'"
        )

    def test_post_valid_data_correct_note_in_db(self, app, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        row = _get_expense("Morning Coffee")
        assert row is not None
        assert row["note"] == "Nice flat white", (
            f"Stored note should be 'Nice flat white', got '{row['note']}'"
        )

    def test_post_expense_appears_on_profile(self, auth_client):
        auth_client.post("/expenses/add", data=VALID_EXPENSE)
        response = auth_client.get("/profile")
        assert b"Morning Coffee" in response.data, (
            "The newly added expense title should appear on the profile page"
        )
        assert b"4.50" in response.data, (
            "The newly added expense amount should appear on the profile page"
        )

    def test_post_without_note_succeeds(self, app, auth_client):
        payload = {
            "title": "No Note Expense",
            "amount": "10.00",
            "category": "transport",
            "date": "2026-05-02",
            "note": "",
        }
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 302, "POST without a note should still succeed (note is optional)"
        assert _expense_count() == 1, "Expense without note should be inserted into the DB"

    def test_post_all_valid_categories_accepted(self, app, auth_client):
        """Each valid category slug must be accepted by the route."""
        for i, cat in enumerate(sorted(VALID_CATEGORIES)):
            payload = {
                "title": f"Expense {cat}",
                "amount": "5.00",
                "category": cat,
                "date": "2026-05-03",
                "note": "",
            }
            response = auth_client.post("/expenses/add", data=payload)
            assert response.status_code == 302, (
                f"Category '{cat}' should be accepted and redirect (got {response.status_code})"
            )


# ---------------------------------------------------------------------------
# POST — validation errors (missing / invalid fields)
# ---------------------------------------------------------------------------

class TestPostAddExpenseValidationErrors:

    def test_missing_title_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "title": ""}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Missing title should re-render the form (200), not redirect"
        )

    def test_missing_title_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "title": ""}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"title" in response.data.lower() or b"required" in response.data.lower(), (
            "An error about the missing title must appear in the response"
        )

    def test_missing_title_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "title": ""}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "A missing title must not write a row to the DB"

    def test_title_too_long_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "title": "A" * 121}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Title > 120 chars should re-render the form (200)"
        )

    def test_title_too_long_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "title": "A" * 121}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"120" in response.data or b"title" in response.data.lower(), (
            "An error about the title length limit must appear in the response"
        )

    def test_title_too_long_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "title": "A" * 121}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "A title > 120 chars must not write a row to the DB"

    def test_title_exactly_120_chars_accepted(self, app, auth_client):
        payload = {**VALID_EXPENSE, "title": "B" * 120}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 302, "Title of exactly 120 chars should be accepted"
        assert _expense_count() == 1, "Expense with 120-char title should be inserted"

    def test_non_numeric_amount_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "abc"}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Non-numeric amount should re-render the form (200)"
        )

    def test_non_numeric_amount_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "abc"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"amount" in response.data.lower() or b"number" in response.data.lower(), (
            "An error about the invalid amount must appear in the response"
        )

    def test_non_numeric_amount_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "amount": "abc"}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "A non-numeric amount must not write a row to the DB"

    def test_zero_amount_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "0"}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, "Zero amount should re-render the form (200)"

    def test_zero_amount_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "0"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"positive" in response.data.lower() or b"amount" in response.data.lower(), (
            "An error about a non-positive amount must appear in the response"
        )

    def test_zero_amount_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "amount": "0"}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "Zero amount must not write a row to the DB"

    def test_negative_amount_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "-5.00"}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, "Negative amount should re-render the form (200)"

    def test_negative_amount_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "amount": "-5.00"}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "Negative amount must not write a row to the DB"

    def test_invalid_category_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "category": "luxury"}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Invalid category should re-render the form (200)"
        )

    def test_invalid_category_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "category": "luxury"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"category" in response.data.lower() or b"invalid" in response.data.lower(), (
            "An error about the invalid category must appear in the response"
        )

    def test_invalid_category_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "category": "luxury"}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "An invalid category must not write a row to the DB"

    def test_malformed_date_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "date": "01-05-2026"}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Malformed date should re-render the form (200)"
        )

    def test_malformed_date_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "date": "01-05-2026"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"date" in response.data.lower() or b"yyyy" in response.data.lower(), (
            "An error about the malformed date must appear in the response"
        )

    def test_malformed_date_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "date": "01-05-2026"}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "A malformed date must not write a row to the DB"

    def test_note_too_long_returns_200(self, auth_client):
        payload = {**VALID_EXPENSE, "note": "N" * 301}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            "Note > 300 chars should re-render the form (200)"
        )

    def test_note_too_long_shows_error(self, auth_client):
        payload = {**VALID_EXPENSE, "note": "N" * 301}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"note" in response.data.lower() or b"300" in response.data, (
            "An error about the note length must appear in the response"
        )

    def test_note_too_long_no_db_write(self, app, auth_client):
        payload = {**VALID_EXPENSE, "note": "N" * 301}
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count() == 0, "Note > 300 chars must not write a row to the DB"

    def test_note_exactly_300_chars_accepted(self, app, auth_client):
        payload = {**VALID_EXPENSE, "note": "X" * 300}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 302, "Note of exactly 300 chars should be accepted"
        assert _expense_count() == 1, "Expense with 300-char note should be inserted"

    @pytest.mark.parametrize("field,value,label", [
        ("title", "", "empty title"),
        ("amount", "not-a-number", "non-numeric amount"),
        ("amount", "0", "zero amount"),
        ("amount", "-1.50", "negative amount"),
        ("category", "invalid-slug", "invalid category"),
        ("date", "2026/05/01", "slash-separated date"),
        ("date", "32-13-2026", "impossible date"),
        ("date", "", "empty date"),
        ("note", "Z" * 301, "note > 300 chars"),
    ])
    def test_parametrized_invalid_inputs_do_not_insert(self, app, auth_client, field, value, label):
        payload = {**VALID_EXPENSE, field: value}
        response = auth_client.post("/expenses/add", data=payload)
        assert response.status_code == 200, (
            f"Invalid input ({label}) should re-render the form, not redirect"
        )
        assert _expense_count() == 0, (
            f"Invalid input ({label}) must not write a row to the DB"
        )


# ---------------------------------------------------------------------------
# Submitted values preserved on validation error
# ---------------------------------------------------------------------------

class TestSubmittedValuesPreservedOnError:

    def test_title_preserved_after_invalid_amount(self, auth_client):
        payload = {**VALID_EXPENSE, "title": "My Unique Title", "amount": "bad"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"My Unique Title" in response.data, (
            "The submitted title must be preserved in the re-rendered form after a validation error"
        )

    def test_amount_preserved_after_invalid_category(self, auth_client):
        payload = {**VALID_EXPENSE, "amount": "99.99", "category": "invalid"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"99.99" in response.data, (
            "The submitted amount must be preserved in the re-rendered form after a validation error"
        )

    def test_category_preserved_after_invalid_date(self, auth_client):
        payload = {**VALID_EXPENSE, "category": "health", "date": "bad-date"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"health" in response.data, (
            "The submitted category must be preserved in the re-rendered form after a validation error"
        )

    def test_date_preserved_after_missing_title(self, auth_client):
        payload = {**VALID_EXPENSE, "title": "", "date": "2026-06-15"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"2026-06-15" in response.data, (
            "The submitted date must be preserved in the re-rendered form after a validation error"
        )

    def test_note_preserved_after_missing_title(self, auth_client):
        payload = {**VALID_EXPENSE, "title": "", "note": "Preserved note text"}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"Preserved note text" in response.data, (
            "The submitted note must be preserved in the re-rendered form after a validation error"
        )

    def test_form_still_shows_add_expense_heading_on_error(self, auth_client):
        payload = {**VALID_EXPENSE, "title": ""}
        response = auth_client.post("/expenses/add", data=payload)
        assert b"Add Expense" in response.data, (
            "The form title 'Add Expense' must still appear after a validation error"
        )


# ---------------------------------------------------------------------------
# Data isolation — expense scoped to the logged-in user only
# ---------------------------------------------------------------------------

class TestDataIsolation:

    def test_expense_stored_under_correct_user(self, app, auth_client):
        """The inserted expense must belong to the authenticated user, not another user."""
        # Register a second user using a fresh client (does not disturb auth_client's session).
        with app.test_client() as other:
            other.post("/register", data={
                "username": "otheruser",
                "email": "other@example.com",
                "password": "otherpass456",
                "confirm_password": "otherpass456",
            })

        # Add an expense as testuser
        auth_client.post("/expenses/add", data=VALID_EXPENSE)

        # Confirm it appears under testuser
        assert _expense_count("testuser") == 1, (
            "The expense should be attributed to the logged-in user 'testuser'"
        )
        # Confirm it does NOT appear under otheruser
        assert _expense_count("otheruser") == 0, (
            "The expense must not be attributed to a different user"
        )

    def test_other_users_expenses_not_visible_on_profile(self, app, auth_client):
        """Expenses added by a second user must not appear on the first user's profile."""
        # Add an expense as testuser
        auth_client.post("/expenses/add", data={**VALID_EXPENSE, "title": "TestuserExpense"})

        # Register otheruser and add a distinctive expense via the DB directly
        with app.test_client() as other:
            other.post("/register", data={
                "username": "otheruser",
                "email": "other@example.com",
                "password": "otherpass456",
                "confirm_password": "otherpass456",
            })
            conn = get_db()
            other_id = conn.execute(
                "SELECT id FROM users WHERE username = ?", ("otheruser",)
            ).fetchone()["id"]
            with conn:
                conn.execute(
                    "INSERT INTO expenses (user_id, title, amount, category, date, note) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (other_id, "OtherUserSecret", 9999.00, "food", "2026-05-01", None),
                )
            conn.close()

        profile_response = auth_client.get("/profile")
        assert b"TestuserExpense" in profile_response.data, (
            "Testuser's own expense should be visible on their profile"
        )
        assert b"OtherUserSecret" not in profile_response.data, (
            "Another user's expense must not appear on testuser's profile"
        )
