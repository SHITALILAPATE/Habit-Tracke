import os
import sqlite3
from datetime import date, timedelta, datetime
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, g
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "habits.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-prod")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '🌱',
            current_streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            last_completed TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            completed_on TEXT NOT NULL,
            UNIQUE(habit_id, completed_on),
            FOREIGN KEY(habit_id) REFERENCES habits(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()



# Auth helpers

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_user_id():
    return session.get("user_id")


# Streak logic

def update_streak_on_complete(db, habit):
    today = date.today()
    last = habit["last_completed"]
    last_d = datetime.strptime(last, "%Y-%m-%d").date() if last else None

    if last_d == today:
        return habit["current_streak"], habit["best_streak"]
    if last_d == today - timedelta(days=1):
        new_streak = habit["current_streak"] + 1
    else:
        new_streak = 1
    best = max(habit["best_streak"], new_streak)
    db.execute(
        "UPDATE habits SET current_streak=?, best_streak=?, last_completed=? WHERE id=?",
        (new_streak, best, today.isoformat(), habit["id"]),
    )
    db.execute(
        "INSERT OR IGNORE INTO completions (habit_id, completed_on) VALUES (?, ?)",
        (habit["id"], today.isoformat()),
    )
    db.commit()
    return new_streak, best


def reconcile_streak_on_uncomplete(db, habit):
    today = date.today().isoformat()
    db.execute(
        "DELETE FROM completions WHERE habit_id=? AND completed_on=?",
        (habit["id"], today),
    )
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    row = db.execute(
        "SELECT 1 FROM completions WHERE habit_id=? AND completed_on=?",
        (habit["id"], yesterday),
    ).fetchone()
    new_streak = max(habit["current_streak"] - 1, 0) if row else 0
    last = yesterday if row else None
    db.execute(
        "UPDATE habits SET current_streak=?, last_completed=? WHERE id=?",
        (new_streak, last, habit["id"]),
    )
    db.commit()
    return new_streak


def serialize_habit(h, completed_today):
    return {
        "id": h["id"],
        "name": h["name"],
        "emoji": h["emoji"],
        "current_streak": h["current_streak"],
        "best_streak": h["best_streak"],
        "last_completed": h["last_completed"],
        "completed_today": bool(completed_today),
    }



# Pages

@app.route("/")
def root():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("index.html", username=session.get("username"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("auth.html", mode="login", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            error = "Username (3+) and password (6+) required."
        else:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
                session["user_id"] = cur.lastrowid
                session["username"] = username
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                error = "Username already taken."
    return render_template("auth.html", mode="register", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# API

@app.route("/api/habits", methods=["GET"])
@login_required
def list_habits():
    db = get_db()
    uid = current_user_id()
    today = date.today().isoformat()
    rows = db.execute(
        "SELECT * FROM habits WHERE user_id=? ORDER BY created_at DESC", (uid,)
    ).fetchall()
    done_today = {
        r["habit_id"] for r in db.execute(
            """SELECT c.habit_id FROM completions c
               JOIN habits h ON h.id=c.habit_id
               WHERE h.user_id=? AND c.completed_on=?""",
            (uid, today),
        ).fetchall()
    }
    habits = [serialize_habit(h, h["id"] in done_today) for h in rows]
    total = len(habits)
    done = sum(1 for h in habits if h["completed_today"])
    return jsonify({
        "habits": habits,
        "stats": {
            "total": total,
            "completed_today": done,
            "progress": round((done / total) * 100) if total else 0,
        },
    })


@app.route("/api/habits", methods=["POST"])
@login_required
def create_habit():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    emoji = (data.get("emoji") or "🌱").strip()[:4]
    if not name:
        return jsonify({"error": "Name required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO habits (user_id, name, emoji) VALUES (?, ?, ?)",
        (current_user_id(), name[:80], emoji),
    )
    db.commit()
    h = db.execute("SELECT * FROM habits WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(serialize_habit(h, False)), 201


@app.route("/api/habits/<int:habit_id>", methods=["DELETE"])
@login_required
def delete_habit(habit_id):
    db = get_db()
    db.execute(
        "DELETE FROM habits WHERE id=? AND user_id=?",
        (habit_id, current_user_id()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/habits/<int:habit_id>/toggle", methods=["POST"])
@login_required
def toggle_habit(habit_id):
    db = get_db()
    habit = db.execute(
        "SELECT * FROM habits WHERE id=? AND user_id=?",
        (habit_id, current_user_id()),
    ).fetchone()
    if not habit:
        return jsonify({"error": "Not found"}), 404
    today = date.today().isoformat()
    already = db.execute(
        "SELECT 1 FROM completions WHERE habit_id=? AND completed_on=?",
        (habit_id, today),
    ).fetchone()
    if already:
        reconcile_streak_on_uncomplete(db, habit)
        completed_today = False
    else:
        update_streak_on_complete(db, habit)
        completed_today = True
    h = db.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    return jsonify(serialize_habit(h, completed_today))



if __name__ == "__main__":
    init_db()
    app.run(debug=True)
