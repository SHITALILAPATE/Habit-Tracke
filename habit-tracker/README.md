# Habitly — Flask Habit Tracker

A dark, glassy habit tracker with streaks, progress, confetti, sound, light/dark mode, and a login system. SQLite-backed.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — register an account, add habits, build your streak.

## Structure

```
app.py
requirements.txt
templates/
  index.html       # Dashboard + habit management
  auth.html        # Login / Register
static/
  style.css
  script.js
habits.db          # auto-created on first run
```

## Notes

- Set `SECRET_KEY` env var in production.
- Streaks auto-update: completing today after yesterday +1; gap → reset to 1; un-checking decrements.
- Confetti fires when all habits hit 100% for the day.
