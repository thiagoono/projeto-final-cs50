from countrycode import countrycode
from cs50 import SQL
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, load_countries, login_required

import re

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///todolist.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    countries = load_countries()

    if request.method == "POST":
        # Get the inputs from the user
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        country = request.form.get("country")

        # Checks if the inputs are valid
        if not username:
            return render_template("register.html", countries=countries, error="must provide username")

        if not password:
            return render_template("register.html", countries=countries, error="must provide password")

        if not confirmation:
            return render_template("register.html", countries=countries, error="must confirm your password")

        if not country:
            return render_template("register.html", countries=countries, error="must provide the country")

        if password != confirmation:
            return render_template("register.html", countries=countries, error="Passwords don't match")

        if country not in countries:
            return render_template("register.html", countries=countries, error="Invalid country name")

        # Convert the country name into its country code
        country_code = countrycode(country, origin="country.name.en.regex", destination="iso3c")[0]

        # Checks if the username  already exists
        try:
            db.execute("INSERT INTO users (username, hash, country) VALUES(?, ?, ?)", username, generate_password_hash(password), country_code)
        except ValueError:
            return render_template("register.html", countries=countries, error="Username already exists")

        # Set the user_id in the user's session
        session["user_id"] = db.execute(
            "SELECT id FROM users WHERE username = ?", username)[0]["id"]
        return redirect("/")

    return render_template("register.html", countries=countries)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error="must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error="must provide password")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return render_template("login.html", error="invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")

@app.route("/")
@login_required
def index():
    """Show the home page"""
    selected_date = request.args.get("date")
    if not selected_date:
        selected_date = datetime.now()
    else:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d")

    selected_date = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)

    tasks = db.execute(
        "SELECT id, title, description, time FROM registered_tasks WHERE user_id = ? AND time > ? AND time < ? ORDER BY time ASC",
        session["user_id"],
        selected_date,
        selected_date + timedelta(days=1),
    )

    for task in tasks:
        task["time"] = datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
        task["time"] = task["time"].strftime("%H:%M")

    selected_date = selected_date.strftime("%Y-%m-%d")

    selected_task_id = request.args.get("task")
    selected_task = None

    if selected_task_id:
        task_rows = db.execute(
            "SELECT id, title, description, time FROM registered_tasks WHERE id = ? AND user_id = ?",
            selected_task_id,
            session["user_id"],
        )

        if task_rows:
            selected_task = task_rows[0]
            selected_task["time"] = datetime.strptime(selected_task["time"], "%Y-%m-%d %H:%M:%S")
            selected_task["time_iso"] = selected_task["time"].isoformat(timespec='minutes')
            selected_task["time"] = selected_task["time"].strftime("%d/%m/%Y %H:%M")

    return render_template("index.html", tasks=tasks, selected_date=selected_date, selected_task=selected_task, path=request.path)

@app.route("/new-task")
@login_required
def new_task():
    """Show the new task page"""

    return render_template("new_task.html")

@app.route("/timeline")
@login_required
def timeline():
    """Show the timeline page"""

    return render_template("timeline.html")

@app.route("/recurring-tasks")
@login_required
def recurring_tasks():
    """Show the recurring tasks page"""

    return render_template("recurring_tasks.html")

@app.route("/profile")
@login_required
def profile():
    """Show the profile page"""

    return render_template("profile.html")

@app.route("/action", methods=["POST"])
@login_required
def action():
    """Delete or edit"""
    path = request.form.get("path")
    task_id = request.form.get("task_id")
    date = request.form.get("date")

    action = request.form.get("action")
    if action == "delete":
        db.execute("DELETE FROM registered_tasks WHERE id = ?", task_id)
    elif action == "edit":
        title = request.form.get("title")
        description = request.form.get("description")
        time = request.form.get("time")

        if not title:
            return apology("must provide title", 400)

        if not time:
            return apology("must provide time", 400)

        try:
            time = datetime.fromisoformat(time)
        except ValueError:
            return apology("Invalid time format", 400)

        db.execute(
            "UPDATE registered_tasks SET title = ?, description = ?, time = ? WHERE id = ?",
            title,
            description,
            time,
            task_id,
        )
    else:
        return apology("Invalid action", 400)

    if path == "/":
        path = "index"

    return redirect(url_for(path, date=date))