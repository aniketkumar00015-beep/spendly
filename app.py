import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for
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

    password_hash = generate_password_hash(password)
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


CATEGORY_SLUGS = {
    "food", "transport", "bills", "health",
    "shopping", "entertainment", "other",
}


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

    expense_rows = conn.execute(
        "SELECT id, title, amount, category, date "
        "FROM expenses WHERE user_id = ? "
        "ORDER BY date DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
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
    for row in expense_rows[:6]:
        recent_transactions.append({
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
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
