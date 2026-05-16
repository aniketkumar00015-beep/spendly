import os
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import init_db, get_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
init_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([username, email, password, confirm_password]):
        return render_template("register.html", error="All fields are required.")
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")
    if "@" not in email:
        return render_template("register.html", error="Enter a valid email address.")
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password_hash),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("register.html", error="Username or email already registered.")

    conn.close()
    session["user_id"] = user_id
    session["username"] = username
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="All fields are required.")

    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password FROM users WHERE email = ?", (email,)
    ).fetchone()

    if row is None or not check_password_hash(row["password"], password):
        conn.close()
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = row["id"]
    session["username"] = row["username"]
    conn.close()
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


CATEGORY_SLUGS = {
    "food", "transport", "bills", "health",
    "shopping", "entertainment", "other",
}


def _validate_expense_form(title, amount_str, category, date, note):
    if not title:
        return None, "Title is required."
    if len(title) > 120:
        return None, "Title must be 120 characters or fewer."
    try:
        amount = float(amount_str)
        if amount <= 0:
            return None, "Amount must be a positive number."
    except ValueError:
        return None, "Amount must be a valid number."
    if category not in CATEGORY_SLUGS:
        return None, "Invalid category."
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None, "Date must be in YYYY-MM-DD format."
    if len(note) > 300:
        return None, "Note must be 300 characters or fewer."
    return amount, None


def _category_slug(name):
    slug = (name or "").strip().lower().replace(" ", "-")
    return slug if slug in CATEGORY_SLUGS else "other"


def _initials(username):
    parts = [p for p in (username or "").replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or ""


def _parse_date_filter(args):
    raw_from = args.get("from", "").strip()
    raw_to = args.get("to", "").strip()
    if not (raw_from and raw_to):
        return None, None, False, None
    try:
        dt_from = datetime.strptime(raw_from, "%Y-%m-%d")
        dt_to = datetime.strptime(raw_to, "%Y-%m-%d")
    except ValueError:
        return None, None, False, None
    if dt_from > dt_to:
        return raw_from, raw_to, False, "Start date must be on or before end date."
    return dt_from.strftime("%Y-%m-%d"), dt_to.strftime("%Y-%m-%d"), True, None


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT username, email, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    if user is None:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    filter_from, filter_to, filter_active, filter_error = _parse_date_filter(request.args)

    sql = (
        "SELECT id, title, amount, category, date "
        "FROM expenses WHERE user_id = ?"
    )
    params = [session["user_id"]]
    if filter_active:
        sql += " AND date BETWEEN ? AND ?"
        params += [filter_from, filter_to]
    sql += " ORDER BY date DESC, id DESC"
    expense_rows = conn.execute(sql, params).fetchall()
    conn.close()

    total_spent = sum(row["amount"] for row in expense_rows)
    transaction_count = len(expense_rows)

    category_totals = {}
    for row in expense_rows:
        category_totals[row["category"]] = category_totals.get(row["category"], 0) + row["amount"]

    top_category = max(category_totals, key=category_totals.get) if category_totals else None

    categories = []
    if category_totals:
        max_total = max(category_totals.values())
        for name, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            categories.append({
                "name": name,
                "total": total,
                "percent": (total / max_total) * 100 if max_total else 0,
                "slug": _category_slug(name),
            })

    recent_transactions = []
    for row in (expense_rows if filter_active else expense_rows[:6]):
        recent_transactions.append({
            "id": row["id"],
            "date": _format_date(row["date"]),
            "title": row["title"],
            "category": row["category"],
            "category_slug": _category_slug(row["category"]),
            "amount": row["amount"],
        })

    joined = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S")

    return render_template(
        "profile.html",
        username=user["username"],
        email=user["email"],
        initials=_initials(user["username"]),
        joined_label=joined.strftime("%d %b %Y"),
        total_spent=total_spent,
        transaction_count=transaction_count,
        top_category=top_category,
        categories=categories,
        recent_transactions=recent_transactions,
        filter_from=filter_from,
        filter_to=filter_to,
        filter_from_label=_format_date(filter_from) if filter_from else None,
        filter_to_label=_format_date(filter_to) if filter_to else None,
        filter_active=filter_active,
        filter_error=filter_error,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "expense_form.html",
            form_title="Add Expense",
            action_url=url_for("add_expense"),
            expense=None,
            error=None,
            categories=sorted(CATEGORY_SLUGS),
        )

    title = request.form.get("title", "").strip()
    amount_str = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()

    form_values = {"title": title, "amount": amount_str, "category": category, "date": date, "note": note}
    amount, error = _validate_expense_form(title, amount_str, category, date, note)

    if error:
        return render_template(
            "expense_form.html",
            form_title="Add Expense",
            action_url=url_for("add_expense"),
            expense=form_values,
            error=error,
            categories=sorted(CATEGORY_SLUGS),
        )

    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date, note) VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_id"], title, amount, category, date, note or None),
        )
    conn.close()
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    if user is None:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    expense = conn.execute(
        "SELECT id, title, amount, category, date, note FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"]),
    ).fetchone()

    if expense is None:
        conn.close()
        abort(404)

    if request.method == "GET":
        conn.close()
        return render_template(
            "expense_form.html",
            form_title="Edit Expense",
            action_url=url_for("edit_expense", expense_id=expense_id),
            expense=expense,
            error=None,
            categories=sorted(CATEGORY_SLUGS),
        )

    title = request.form.get("title", "").strip()
    amount_str = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()

    form_values = {"title": title, "amount": amount_str, "category": category, "date": date, "note": note}
    amount, error = _validate_expense_form(title, amount_str, category, date, note)

    if error:
        conn.close()
        return render_template(
            "expense_form.html",
            form_title="Edit Expense",
            action_url=url_for("edit_expense", expense_id=expense_id),
            expense=form_values,
            error=error,
            categories=sorted(CATEGORY_SLUGS),
        )

    with conn:
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=?, date=?, note=? WHERE id=? AND user_id=?",
            (title, amount, category, date, note or None, expense_id, session["user_id"]),
        )
    conn.close()
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/delete")
def delete_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()
    expense = conn.execute(
        "SELECT id FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"]),
    ).fetchone()

    if expense is None:
        conn.close()
        abort(404)

    with conn:
        conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, session["user_id"]),
        )
    conn.close()
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
