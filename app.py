from countrycode import countrycode
from cs50 import SQL
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, load_countries, login_required

import re
import json

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

    registered_tasks = db.execute(
        "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE user_id = ? AND start_time >= ? AND end_time <= ? ORDER BY start_time ASC",
        session["user_id"],
        selected_date,
        selected_date + timedelta(days=1),
    )

    recurrent_tasks = db.execute(
        "SELECT id, title, description, start_time, end_time, recurrency, days FROM recurrent_tasks WHERE user_id = ? AND " \
        "(recurrency = 'daily' OR (recurrency = 'weekly' AND days LIKE ?) OR (recurrency = 'monthly' AND days LIKE ?)) ORDER BY start_time ASC",
        session["user_id"],
        f"%{selected_date.strftime('%A')}%",
        f"%{selected_date.day}%"
    )

    tasks = []

    for task in registered_tasks:
        tasks.append({
            "id": task["id"],
            "title": task["title"],
            "description": task["description"],
            "start_time": task["start_time"],
            "end_time": task["end_time"],
            "recurrency": None,
            "days": None
        })

    for task in recurrent_tasks:
        tasks.append({
            "id": task["id"],
            "title": task["title"],
            "description": task["description"],
            "start_time": selected_date.strftime("%Y-%m-%d") + " " + task["start_time"],
            "end_time": selected_date.strftime("%Y-%m-%d") + " " + task["end_time"],
            "recurrency": task["recurrency"],
            "days": task["days"]
        })

    for task in tasks:
        task["start_time"] = datetime.strptime(task["start_time"], "%Y-%m-%d %H:%M")
        task["start_time"] = task["start_time"].strftime("%H:%M")

        task["end_time"] = datetime.strptime(task["end_time"], "%Y-%m-%d %H:%M")
        task["end_time"] = task["end_time"].strftime("%H:%M")

    tasks.sort(key=lambda x: x["start_time"])

    selected_date = selected_date.strftime("%Y-%m-%d")

    selected_task_id = request.args.get("task")
    selected_task = None

    if selected_task_id:
        task_rows = db.execute(
            "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE id = ?",
            selected_task_id
        )

        if task_rows:
            selected_task = task_rows[0]
            selected_task["start_time"] = datetime.strptime(selected_task["start_time"], "%Y-%m-%d %H:%M")
            selected_task["start_time_iso"] = selected_task["start_time"].isoformat(timespec='minutes')
            selected_task["start_time"] = selected_task["start_time"].strftime("%d/%m/%Y %H:%M")

            selected_task["end_time"] = datetime.strptime(selected_task["end_time"], "%Y-%m-%d %H:%M")
            selected_task["end_time_iso"] = selected_task["end_time"].isoformat(timespec='minutes')
            selected_task["end_time"] = selected_task["end_time"].strftime("%d/%m/%Y %H:%M")

    return render_template(
        "index.html",
        tasks=tasks,
        selected_date=selected_date,
        selected_task=selected_task,
        path=request.path,
        error=request.args.get("error"),
    )

@app.route("/new-task", methods=["GET", "POST"])
@login_required
def new_task():
    """Show the new task page or create a new task."""

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if not title:
            # HERE
            return redirect(url_for("new_task", error="must provide title"))

        if not start_time or not end_time:
            # HERE
            return redirect(url_for("new_task", error="must provide start and end time"))

        try:
            start_time = datetime.fromisoformat(start_time)
        except ValueError:
            return apology("Invalid time format", 400)

        try:
            end_time = datetime.fromisoformat(end_time)
        except ValueError:
            return apology("Invalid time format", 400)

        if start_time >= end_time:
            # HERE
            return redirect(url_for("new_task", error="Start time must be before end time"))

        search_existing_tasks = db.execute(
            "SELECT * FROM registered_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?))",
            session["user_id"],
            start_time,
            start_time,
            end_time,
            end_time,
            start_time,
            end_time,
        )

        if search_existing_tasks:
            # HERE
            return redirect(url_for("new_task", error="Task conflicts with existing task"))

        start_time = start_time.strftime("%Y-%m-%d %H:%M")
        end_time = end_time.strftime("%Y-%m-%d %H:%M")

        db.execute(
            "INSERT INTO registered_tasks (user_id, title, description, start_time, end_time) VALUES(?, ?, ?, ?, ?)",
            session["user_id"],
            title,
            description,
            start_time,
            end_time,
        )

        return redirect(url_for("index"))

    return render_template("new_task.html", error=request.args.get("error"))

@app.route("/timeline")
@login_required
def timeline():
    """Show the timeline page"""

    return render_template("timeline.html")

@app.route("/recurring-tasks", methods=["GET", "POST"])
@app.route("/recurring_tasks", methods=["GET", "POST"])
@login_required
def recurring_tasks():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        recurrence_type = request.form.get("repeat_interval")

        if recurrence_type == "weekly":
            repeat_days = request.form.getlist("repeat_days_week")
        elif recurrence_type == "monthly":
            repeat_days = request.form.getlist("repeat_days_month")
        elif recurrence_type == "daily":
            repeat_days = []
        else:
            return redirect(url_for("recurring_tasks", error="Invalid recurrence type"))

        if not title:
            return redirect(url_for("recurring_tasks", error="must provide title"))

        if not start_time or not end_time:
            return redirect(url_for("recurring_tasks", error="must provide start and end time"))

        time_pattern = r"^([0-1][0-9]|[2][0-3]):[0-5][0-9]$"

        if not re.match(time_pattern, start_time):
            return redirect(url_for("recurring_tasks", error="Invalid start time format"))

        if not re.match(time_pattern, end_time):
            return redirect(url_for("recurring_tasks", error="Invalid end time format"))

        # TODO: Validate that start_time is before end_time

        if recurrence_type not in ["daily", "weekly", "monthly"]:
            return redirect(url_for("recurring_tasks", error="Invalid recurrence type"))

        if recurrence_type == "weekly" and not repeat_days:
            return redirect(url_for("recurring_tasks", error="Must select at least one day for weekly recurrence"))

        if recurrence_type == "monthly" and (not repeat_days or not all(day.isdigit() and 1 <= int(day) <= 31 for day in repeat_days)):
            return redirect(url_for("recurring_tasks", error="Must select valid days for monthly recurrence"))

        # Insert the recurring task into the database
        db.execute(
            "INSERT INTO recurrent_tasks (user_id, title, description, start_time, end_time, recurrency, days) VALUES(?, ?, ?, ?, ?, ?, ?)",
            session["user_id"],
            title,
            description,
            start_time,
            end_time,
            recurrence_type,
            " ".join(repeat_days)
        )

        return redirect(url_for("recurring_tasks"))

    recurring_tasks_rows = db.execute(
        "SELECT id, title, description, start_time, end_time, recurrency, days FROM recurrent_tasks WHERE user_id = ? ORDER BY start_time ASC"  ,
        session["user_id"],
    )

    for task in recurring_tasks_rows:
        task["days"] = [day.strip().title() for day in task["days"].split(" ") if day.strip()]

    return render_template("recurring_tasks.html", recurring_tasks=recurring_tasks_rows, error=request.args.get("error"))

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
    redirect_endpoint = "index" if path == "/" else ((path or "").lstrip("/") or "index")

    if action == "delete":
        db.execute("DELETE FROM registered_tasks WHERE id = ?", task_id)
    elif action == "edit":
        title = request.form.get("title")
        description = request.form.get("description")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if not title:
            # HERE
            return redirect(url_for(redirect_endpoint, date=date, task=task_id, error="must provide title"))

        if not start_time or not end_time:
            # HERE
            return redirect(url_for(redirect_endpoint, date=date, task=task_id, error="must provide start and end time"))

        try:
            start_time = datetime.fromisoformat(start_time)
            end_time = datetime.fromisoformat(end_time)
        except ValueError:
            return apology("Invalid time format", 400)

        if start_time >= end_time:
            # HERE
            return redirect(url_for(redirect_endpoint, date=date, task=task_id, error="Start time must be before end time"))

        search_existing_tasks = db.execute(
            "SELECT * FROM registered_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?))",
            session["user_id"],
            start_time,
            start_time,
            end_time,
            end_time,
            start_time,
            end_time,
        )

        if search_existing_tasks:
            # HERE
            return redirect(url_for(redirect_endpoint, date=date, task=task_id, error="Task conflicts with existing task"))

        start_time = start_time.strftime("%Y-%m-%d %H:%M")
        end_time = end_time.strftime("%Y-%m-%d %H:%M")

        db.execute(
            "UPDATE registered_tasks SET title = ?, description = ?, start_time = ?, end_time = ? WHERE id = ?",
            title,
            description,
            start_time,
            end_time,
            task_id,
        )
    else:
        return apology("Invalid action", 400)

    if path == "/":
        path = "index"

    return redirect(url_for(path, date=date))