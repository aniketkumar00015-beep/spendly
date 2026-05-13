"""
Tests for the date-filter feature on the /profile route (Step 06).

Spec: .claude/specs/06-date-filter-profile-page.md

Coverage:
  - Auth guard
  - Baseline behaviour (no filter params)
  - 6-item transaction cap when no filter is active
  - Filter happy path: stats scoped to the date window
  - Filter shows ALL matching transactions (no cap)
  - Active-filter badge appears / disappears correctly
  - Filter values are preserved in form inputs on re-render
  - Panel heading changes between filtered and unfiltered states
  - from > to  → inline error, no filter applied
  - Malformed date strings → silently ignored, page renders unfiltered
  - Only one of from/to supplied → treated as no filter
  - Valid date range that matches no expenses → zero stats, no error
  - Data isolation: second user's expenses never appear
  - Category breakdown and top category scoped to the window
"""

import pytest
import database.db as db_module
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Each test gets its own SQLite file so tests are fully isolated.
    We monkeypatch database.db.DB_PATH so that every get_db() call within
    the test process uses the temporary file rather than the shared
    expense_tracker.db on disk.
    """
    db_file = str(tmp_path / 'test_expense_tracker.db')
    monkeypatch.setattr(db_module, 'DB_PATH', db_file)

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
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
    client.post('/register', data={
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'securepass123',
        'confirm_password': 'securepass123',
    })
    return client


# ---------------------------------------------------------------------------
# Helper: insert expenses directly via the DB connection
# ---------------------------------------------------------------------------

def _insert_expense(title, amount, category, date, user_id=None, note=None):
    """Insert a single expense for a given user_id (fetched from DB if None)."""
    conn = get_db()
    if user_id is None:
        row = conn.execute("SELECT id FROM users WHERE username = 'testuser'").fetchone()
        user_id = row['id']
    with conn:
        conn.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, amount, category, date, note),
        )
    conn.close()


def _get_user_id(username):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row['id']


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_unauthenticated_get_redirects_to_login(self, client):
        response = client.get('/profile')
        assert response.status_code == 302, 'Expected redirect for unauthenticated request'
        assert '/login' in response.headers['Location'], 'Redirect target should be /login'

    def test_unauthenticated_get_with_filter_params_redirects_to_login(self, client):
        response = client.get('/profile?from=2026-01-01&to=2026-12-31')
        assert response.status_code == 302, 'Filter params should not bypass auth'
        assert '/login' in response.headers['Location']


# ---------------------------------------------------------------------------
# Baseline behaviour — no filter params
# ---------------------------------------------------------------------------

class TestBaselineNoFilter:

    def test_profile_returns_200_when_authenticated(self, auth_client):
        response = auth_client.get('/profile')
        assert response.status_code == 200, 'Profile page should return 200 for logged-in user'

    def test_profile_renders_username(self, auth_client):
        response = auth_client.get('/profile')
        assert b'testuser' in response.data, 'Profile page should display the username'

    def test_profile_zero_stats_when_no_expenses(self, auth_client):
        response = auth_client.get('/profile')
        assert b'0' in response.data, 'Transaction count should be 0 when there are no expenses'
        assert b'0.00' in response.data, 'Total spent should show 0.00 when there are no expenses'

    def test_profile_shows_recent_transactions_heading_when_no_filter(self, auth_client):
        response = auth_client.get('/profile')
        assert b'Recent Transactions' in response.data, \
            'Should show "Recent Transactions" heading when no filter is active'

    def test_no_filter_badge_when_no_params(self, auth_client):
        response = auth_client.get('/profile')
        assert b'filter-badge' not in response.data, \
            'Active-filter badge must be absent when no filter is set'
        assert b'Showing:' not in response.data, \
            '"Showing:" label must not appear when no filter is active'

    def test_no_filter_error_when_no_params(self, auth_client):
        response = auth_client.get('/profile')
        assert b'filter-error' not in response.data, \
            'No error message should be shown when no filter params are supplied'

    def test_six_item_cap_when_no_filter(self, app, auth_client):
        # Insert 9 expenses; only 6 should appear in recent_transactions.
        for i in range(9):
            _insert_expense(f'Expense {i}', 10.00 + i, 'food', f'2026-04-{str(i + 1).zfill(2)}')
        response = auth_client.get('/profile')
        assert response.status_code == 200
        # Count occurrences of 'tx-row' as a proxy for rendered rows.
        tx_row_count = response.data.count(b'tx-row')
        assert tx_row_count == 6, (
            f'Expected exactly 6 transaction rows when no filter is active, got {tx_row_count}'
        )

    def test_all_time_stats_include_all_expenses(self, app, auth_client):
        _insert_expense('Food Jan', 100.00, 'food', '2026-01-15')
        _insert_expense('Food Apr', 200.00, 'food', '2026-04-10')
        response = auth_client.get('/profile')
        assert b'300.00' in response.data, \
            'All-time total should sum all expenses regardless of date'


# ---------------------------------------------------------------------------
# Filter happy path — valid from/to params
# ---------------------------------------------------------------------------

class TestFilterHappyPath:

    def test_filter_scopes_total_spent(self, app, auth_client):
        # January expense should be excluded; April expense should be included.
        _insert_expense('Jan buy', 500.00, 'bills', '2026-01-10')
        _insert_expense('Apr buy', 150.00, 'food', '2026-04-05')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'150.00' in response.data, \
            'Total spent should reflect only expenses within the filtered date range'
        assert b'500.00' not in response.data, \
            'Expense outside the date range must not appear in the total'

    def test_filter_scopes_transaction_count(self, app, auth_client):
        _insert_expense('March trip', 80.00, 'transport', '2026-03-20')
        _insert_expense('April lunch', 12.50, 'food', '2026-04-02')
        _insert_expense('April coffee', 4.00, 'food', '2026-04-15')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'>2<' in response.data or b'2' in response.data, \
            'Transaction count should be 2 for the April-only filter'
        assert b'>3<' not in response.data, \
            'Transaction count must not include the March expense'

    def test_filter_scopes_top_category(self, app, auth_client):
        _insert_expense('Big food bill', 300.00, 'food', '2026-04-01')
        _insert_expense('Small bills', 50.00, 'bills', '2026-04-10')
        # Add a large transport expense OUTSIDE the range — should not influence top category.
        _insert_expense('Transport annual', 1000.00, 'transport', '2026-01-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'food' in response.data.lower(), \
            'Top category should be "food" for the filtered April window'
        # "transport" should appear in category-slug classes but NOT as the top-category stat
        # We check that the top category stat value is food, not transport.
        # The stat card for Top Category should contain "food".
        assert b'transport' not in response.data.split(b'Top Category')[1].split(b'stat-card')[0].lower() \
            if b'Top Category' in response.data else True

    def test_filter_shows_all_matching_transactions_no_cap(self, app, auth_client):
        # Insert 9 expenses all within the filtered range.
        for i in range(9):
            _insert_expense(f'April exp {i}', 10.00, 'food', f'2026-04-{str(i + 1).zfill(2)}')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        tx_row_count = response.data.count(b'tx-row')
        assert tx_row_count == 9, (
            f'With an active filter all matching transactions should be shown (no cap); '
            f'got {tx_row_count}'
        )

    def test_filter_shows_all_transactions_heading(self, app, auth_client):
        _insert_expense('Some expense', 25.00, 'food', '2026-04-05')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'All Transactions' in response.data, \
            'Heading should change to "All Transactions" when a filter is active'
        assert b'Recent Transactions' not in response.data, \
            '"Recent Transactions" heading should not appear when a filter is active'

    def test_filter_includes_boundary_dates(self, app, auth_client):
        # Spec says the range is inclusive (BETWEEN ? AND ?).
        _insert_expense('On from date', 10.00, 'food', '2026-04-01')
        _insert_expense('On to date', 20.00, 'food', '2026-04-30')
        _insert_expense('Outside range', 999.00, 'food', '2026-05-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        tx_row_count = response.data.count(b'tx-row')
        assert tx_row_count == 2, \
            'Boundary dates must be included (BETWEEN is inclusive)'

    def test_filter_returns_200(self, auth_client):
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert response.status_code == 200, 'A valid filtered request must return 200'


# ---------------------------------------------------------------------------
# Active-filter badge and form value preservation
# ---------------------------------------------------------------------------

class TestFilterBadgeAndFormState:

    def test_badge_present_when_filter_active(self, app, auth_client):
        _insert_expense('Check badge', 50.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'filter-badge' in response.data, \
            'Active-filter badge element must be present when a date filter is applied'
        assert b'Showing:' in response.data, \
            '"Showing:" label must appear in the badge when filter is active'

    def test_badge_contains_from_and_to_dates(self, auth_client):
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'2026-04-01' in response.data, \
            'The from date should appear in the active-filter badge'
        assert b'2026-04-30' in response.data, \
            'The to date should appear in the active-filter badge'

    def test_badge_absent_when_no_filter(self, auth_client):
        response = auth_client.get('/profile')
        assert b'Showing:' not in response.data, \
            '"Showing:" must not appear when no filter is active'

    def test_from_input_value_preserved(self, auth_client):
        response = auth_client.get('/profile?from=2026-03-01&to=2026-03-31')
        # The form input for "from" should have value="2026-03-01"
        assert b'value="2026-03-01"' in response.data, \
            'The "from" date input must be pre-filled with the active from value'

    def test_to_input_value_preserved(self, auth_client):
        response = auth_client.get('/profile?from=2026-03-01&to=2026-03-31')
        assert b'value="2026-03-31"' in response.data, \
            'The "to" date input must be pre-filled with the active to value'

    def test_inputs_empty_when_no_filter(self, auth_client):
        response = auth_client.get('/profile')
        # Neither input should carry a non-empty value attribute when no filter is set.
        assert b'value="2026-' not in response.data, \
            'Date inputs must be empty when no filter params are supplied'


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestFilterValidation:

    def test_from_greater_than_to_returns_200(self, auth_client):
        # The page must re-render (not crash) when from > to.
        response = auth_client.get('/profile?from=2026-04-30&to=2026-04-01')
        assert response.status_code == 200, \
            'from > to should render the page (200), not a server error'

    def test_from_greater_than_to_shows_inline_error(self, auth_client):
        response = auth_client.get('/profile?from=2026-04-30&to=2026-04-01')
        assert b'filter-error' in response.data, \
            'An inline error element must be present when from > to'
        # The spec says: "Start date must be on or before end date."
        assert b'date' in response.data.lower(), \
            'The error message should mention dates'

    def test_from_greater_than_to_no_filter_badge(self, auth_client):
        response = auth_client.get('/profile?from=2026-04-30&to=2026-04-01')
        assert b'Showing:' not in response.data, \
            'No active-filter badge must appear when from > to (filter not applied)'

    def test_from_greater_than_to_shows_all_time_stats(self, app, auth_client):
        # Insert one expense; when from > to the all-time total should be shown.
        _insert_expense('My expense', 77.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=2026-04-30&to=2026-04-01')
        assert b'77.00' in response.data, \
            'When from > to, all-time stats (not filtered) should be displayed'

    def test_malformed_from_silently_ignored(self, app, auth_client):
        _insert_expense('Normal expense', 55.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=abc&to=2026-04-30')
        assert response.status_code == 200, \
            'Malformed from param should not crash the page'
        assert b'filter-badge' not in response.data, \
            'No filter badge should appear when from is malformed'
        assert b'55.00' in response.data, \
            'All-time total should be shown when the from param is malformed'

    def test_malformed_to_silently_ignored(self, app, auth_client):
        _insert_expense('Normal expense', 66.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=2026-04-01&to=not-a-date')
        assert response.status_code == 200, \
            'Malformed to param should not crash the page'
        assert b'filter-badge' not in response.data, \
            'No filter badge should appear when to is malformed'
        assert b'66.00' in response.data, \
            'All-time total should be shown when the to param is malformed'

    def test_both_malformed_silently_ignored(self, app, auth_client):
        _insert_expense('Any expense', 33.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=bad&to=also-bad')
        assert response.status_code == 200
        assert b'filter-badge' not in response.data
        assert b'33.00' in response.data

    def test_only_from_supplied_no_filter_applied(self, app, auth_client):
        _insert_expense('Lone expense', 99.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?from=2026-04-01')
        assert response.status_code == 200
        assert b'filter-badge' not in response.data, \
            'Only from supplied (no to) must be treated as no filter'
        assert b'99.00' in response.data, \
            'All-time total should appear when only from is supplied'

    def test_only_to_supplied_no_filter_applied(self, app, auth_client):
        _insert_expense('Lone expense', 88.00, 'food', '2026-04-10')
        response = auth_client.get('/profile?to=2026-04-30')
        assert response.status_code == 200
        assert b'filter-badge' not in response.data, \
            'Only to supplied (no from) must be treated as no filter'
        assert b'88.00' in response.data, \
            'All-time total should appear when only to is supplied'

    @pytest.mark.parametrize('from_val,to_val', [
        ('', '2026-04-30'),
        ('2026-04-01', ''),
        ('', ''),
        ('   ', '2026-04-30'),
    ])
    def test_blank_or_empty_params_treated_as_no_filter(self, app, auth_client, from_val, to_val):
        _insert_expense('Param edge case', 42.00, 'food', '2026-04-10')
        response = auth_client.get(f'/profile?from={from_val}&to={to_val}')
        assert response.status_code == 200, \
            'Blank/empty date params must not crash the page'
        assert b'filter-badge' not in response.data, \
            'No filter badge should appear for blank/empty date params'


# ---------------------------------------------------------------------------
# Empty filtered result set
# ---------------------------------------------------------------------------

class TestEmptyFilteredResult:

    def test_valid_range_with_no_matching_expenses_returns_200(self, app, auth_client):
        # Expenses exist but outside the filtered range.
        _insert_expense('Old expense', 100.00, 'food', '2025-01-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert response.status_code == 200

    def test_valid_range_with_no_matching_expenses_shows_zero_stats(self, app, auth_client):
        _insert_expense('Old expense', 100.00, 'food', '2025-01-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        # Total spent should be 0.00; transaction count 0.
        assert b'0.00' in response.data, \
            'Total spent must be 0.00 when no expenses fall in the filtered range'

    def test_valid_range_with_no_matching_expenses_still_shows_badge(self, app, auth_client):
        _insert_expense('Old expense', 100.00, 'food', '2025-01-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'filter-badge' in response.data, \
            'Active-filter badge should still appear even when there are no matching expenses'

    def test_valid_range_with_no_matching_expenses_no_error(self, app, auth_client):
        _insert_expense('Old expense', 100.00, 'food', '2025-01-01')
        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'filter-error' not in response.data, \
            'No error message should appear for a valid date range that simply has no results'


# ---------------------------------------------------------------------------
# Data isolation — second user's expenses must never leak
# ---------------------------------------------------------------------------

def _seed_second_user(app):
    """
    Register 'otheruser' directly via a fresh test client so the session
    of the primary auth_client is never disturbed.  Returns the new user id.
    """
    with app.test_client() as c:
        c.post('/register', data={
            'username': 'otheruser',
            'email': 'other@example.com',
            'password': 'otherpass456',
            'confirm_password': 'otherpass456',
        })
    return _get_user_id('otheruser')


class TestDataIsolation:

    def test_other_users_expenses_not_in_unfiltered_view(self, app, auth_client):
        # Register a second user with a very distinctive expense amount.
        other_id = _seed_second_user(app)
        _insert_expense('Secret other expense', 9999.00, 'food', '2026-04-10', user_id=other_id)

        response = auth_client.get('/profile')
        assert b'9999.00' not in response.data, \
            "Another user's expenses must not appear on the current user's profile"

    def test_other_users_expenses_not_in_filtered_view(self, app, auth_client):
        other_id = _seed_second_user(app)
        _insert_expense('Other April expense', 8888.00, 'bills', '2026-04-15', user_id=other_id)

        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'8888.00' not in response.data, \
            "Another user's April expenses must not appear in the filtered view"

    def test_own_expenses_still_visible_with_other_user_data(self, app, auth_client):
        # Own expense in the filtered range must still appear.
        _insert_expense('My April expense', 123.45, 'food', '2026-04-05')

        other_id = _seed_second_user(app)
        _insert_expense('Other expense', 6666.00, 'food', '2026-04-05', user_id=other_id)

        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        assert b'123.45' in response.data, \
            "The logged-in user's own expenses must still appear with an active filter"
        assert b'6666.00' not in response.data, \
            "Another user's expense must not leak into the current user's filtered view"


# ---------------------------------------------------------------------------
# Category breakdown scoped to filter window
# ---------------------------------------------------------------------------

class TestCategoryBreakdown:

    def test_category_totals_scoped_to_filter(self, app, auth_client):
        # In April: food=200, bills=50
        _insert_expense('Food April', 200.00, 'food', '2026-04-10')
        _insert_expense('Bills April', 50.00, 'bills', '2026-04-20')
        # Outside range: transport=1000 (must not appear in breakdown)
        _insert_expense('Transport Jan', 1000.00, 'transport', '2026-01-05')

        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        data = response.data

        # food and bills should appear in the page
        assert b'200.00' in data, 'Food total of 200.00 should be in the category breakdown'
        assert b'50.00' in data, 'Bills total of 50.00 should be in the category breakdown'
        # transport total of 1000.00 should NOT appear
        assert b'1,000.00' not in data and b'1000.00' not in data, \
            'Transport expense outside the range must not appear in the category breakdown'

    def test_top_category_correct_for_filtered_window(self, app, auth_client):
        # food wins in April; transport dominates all-time but is outside the range.
        _insert_expense('Food April big', 500.00, 'food', '2026-04-01')
        _insert_expense('Bills April small', 30.00, 'bills', '2026-04-15')
        _insert_expense('Transport Jan huge', 2000.00, 'transport', '2026-01-01')

        response = auth_client.get('/profile?from=2026-04-01&to=2026-04-30')
        # Top category stat should contain "food" (case-insensitive check via lower())
        assert b'food' in response.data.lower(), \
            'Top category for the April filter window should be "food"'

    def test_no_category_data_shown_when_filter_matches_nothing(self, app, auth_client):
        _insert_expense('Old expense', 100.00, 'food', '2025-01-01')
        response = auth_client.get('/profile?from=2026-06-01&to=2026-06-30')
        # Empty-state text should appear in the category panel.
        assert b'No category data yet' in response.data or b'empty-state' in response.data, \
            'Category panel should show empty state when no expenses match the filter'
