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

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
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

    selected_task_id = request.args.get("task")
    selected_task = None

    recurrent = False

    if selected_task_id:
        recurrent = request.args.get("recurrent")

        if recurrent == "False":
            task_rows = db.execute(
                "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE id = ? AND user_id = ?",
                selected_task_id,
                session["user_id"]
            )
            recurrent = False
        else:
            task_rows = db.execute(
                "SELECT id, title, description, start_time, end_time, recurrency, days FROM recurrent_tasks WHERE id = ? AND user_id = ?",
                selected_task_id,
                session["user_id"]
            )
            recurrent = True

        if not task_rows:
            return apology("Task not found", 404)

        selected_task = task_rows[0]

        if recurrent:
            selected_task["start_time"] = datetime.strptime(selected_task["start_time"], "%H:%M")
            selected_task["start_time"] = selected_task["start_time"].replace(year=selected_date.year, month=selected_date.month, day=selected_date.day)

            selected_task["end_time"] = datetime.strptime(selected_task["end_time"], "%H:%M")
            selected_task["end_time"] = selected_task["end_time"].replace(year=selected_date.year, month=selected_date.month, day=selected_date.day)
        else:
            selected_task["start_time"] = datetime.strptime(selected_task["start_time"], "%Y-%m-%d %H:%M")
            selected_task["end_time"] = datetime.strptime(selected_task["end_time"], "%Y-%m-%d %H:%M")

        selected_task["start_time_iso"] = selected_task["start_time"].isoformat(timespec='minutes')
        selected_task["start_time"] = selected_task["start_time"].strftime("%d/%m/%Y %H:%M")

        selected_task["end_time_iso"] = selected_task["end_time"].isoformat(timespec='minutes')
        selected_task["end_time"] = selected_task["end_time"].strftime("%d/%m/%Y %H:%M")

    selected_date = selected_date.strftime("%Y-%m-%d")
    
    if request.method == "GET":
        """Show the home page"""
        return render_template(
            "index.html",
            tasks=tasks,
            selected_date=selected_date,
            selected_task=selected_task,
            error=request.args.get("error"),
            recurrent=recurrent,
        )

    elif request.method == "POST":
        task_id = request.form.get("task_id")
        date = request.form.get("date")
        table = request.form.get("table")
        force_conflict = request.form.get("force_conflict") == "1"
    
        action = request.form.get("action")
        if action == "delete":
            recurrency = request.form.get("recurrency")

            if recurrency:
                db.execute(
                    "DELETE FROM recurrent_tasks WHERE id = ? AND user_id = ?",
                    task_id,
                    session["user_id"]
                )
            else:
                db.execute(
                    "DELETE FROM registered_tasks WHERE id = ? AND user_id = ?",
                    task_id,
                    session["user_id"]
                )
        
        elif action == "edit":
            title = request.form.get("title")
            description = request.form.get("description")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")

            if not title:
                return render_template(
                    "index.html", 
                    error="must provide title", 
                    selected_date=date, 
                    selected_task={
                        "id": task_id, 
                        "title": title, 
                        "description": description, 
                        "start_time": start_time, 
                        "end_time": end_time
                    }, 
                )

            if not start_time or not end_time:
                return render_template(
                    "index.html", 
                    error="must provide start and end time", 
                    selected_date=date, 
                    selected_task={
                        "id": task_id, 
                        "title": title, 
                        "description": description, 
                        "start_time": start_time, 
                        "end_time": end_time
                    }, 
                )

            if table == "registered_tasks":
                try:
                    start_time = datetime.fromisoformat(start_time)
                    end_time = datetime.fromisoformat(end_time)
                except ValueError:
                    return apology("Invalid time format", 400)
        
                if start_time >= end_time:
                    return render_template(
                        "index.html", 
                        error="Start time must be before end time", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
                
                search_existing_registered_tasks = db.execute(
                    "SELECT * FROM registered_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND id != ?",
                    session["user_id"],
                    start_time,
                    start_time,
                    end_time,
                    end_time,
                    start_time,
                    end_time,
                    task_id
                )
            
                search_existing_recurrent_tasks = db.execute(
                    "SELECT * FROM recurrent_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND (recurrency = 'daily' OR (recurrency = 'weekly' AND days LIKE ?) OR (recurrency = 'monthly' AND days LIKE ?))",
                    session["user_id"],
                    start_time.strftime("%H:%M"),
                    start_time.strftime("%H:%M"),
                    end_time.strftime("%H:%M"),
                    end_time.strftime("%H:%M"),
                    start_time.strftime("%H:%M"),
                    end_time.strftime("%H:%M"),
                    f"%{start_time.strftime('%A')}%",
                    f"%{start_time.strftime('%d')}%",
                )
            
                if (search_existing_registered_tasks or search_existing_recurrent_tasks) and not force_conflict:
                    conflicting_tasks = [task for task in search_existing_registered_tasks] + [task for task in search_existing_recurrent_tasks]
                    return render_template(
                        "index.html", 
                        date=date, 
                        task=task_id, 
                        conflict_tasks=conflicting_tasks, 
                        recurrent="False", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time.strftime("%d/%m/%Y %H:%M"),
                            "end_time": end_time.strftime("%d/%m/%Y %H:%M"),
                            "start_time_form": start_time.isoformat(timespec="minutes"),
                            "end_time_form": end_time.isoformat(timespec="minutes")
                        }, 
                    )

                start_time = start_time.strftime("%Y-%m-%d %H:%M")
                end_time = end_time.strftime("%Y-%m-%d %H:%M")

                db.execute(
                    "UPDATE registered_tasks SET title = ?, description = ?, start_time = ?, end_time = ? WHERE id = ? AND user_id = ?",
                    title,
                    description,
                    start_time,
                    end_time,
                    task_id,
                    session["user_id"]
                )

            elif table == "recurrent_tasks":
                time_pattern = r"^([0-1][0-9]|[2][0-3]):[0-5][0-9]$"
                            
                if not re.match(time_pattern, start_time):
                    return render_template(
                        "index.html", 
                        error="Invalid start time format", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
        
                if not re.match(time_pattern, end_time):
                    return render_template(
                        "index.html", 
                        error="Invalid end time format", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
        
                if start_time >= end_time:
                    return render_template(
                        "index.html", 
                        error="Start time must be before end time", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
                
                recurrence_type = request.form.get("recurrency")
                repeat_days = db.execute("SELECT days FROM recurrent_tasks WHERE id = ? AND user_id = ?", task_id, session["user_id"])[0]["days"].split(" ")
    
                if recurrence_type == "weekly":
                    repeat_days = request.form.getlist("repeat_days_week")
                elif recurrence_type == "monthly":
                    repeat_days = request.form.getlist("repeat_days_month")
                elif recurrence_type == "daily":
                    repeat_days = []
                else:
                    return render_template(
                        "index.html", 
                        error="Invalid recurrence type", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
    
                if recurrence_type == "weekly" and not repeat_days:
                    return render_template(
                        "index.html", 
                        error="Must select at least one day for weekly recurrence", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
    
                if recurrence_type == "monthly" and (not repeat_days or not all(day.isdigit() and 1 <= int(day) <= 31 for day in repeat_days)):
                    return render_template(
                        "index.html", 
                        error="Must select valid days for monthly recurrence", 
                        selected_date=date, 
                        selected_task={
                            "id": task_id, 
                            "title": title, 
                            "description": description, 
                            "start_time": start_time, 
                            "end_time": end_time
                        }, 
                    )
    
                # CHECK FOR CONFLICTS WITH OTHER recurrent TASKS
                command_for_recurrent = "SELECT * FROM recurrent_tasks WHERE user_id = ? AND id != ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND (recurrency = 'daily'"
    
                if recurrence_type == "daily":
                    command_for_recurrent += ")"
                elif recurrence_type == "weekly":
                    command_for_recurrent += " OR (recurrency = 'weekly' AND (" + " OR ".join(f"days LIKE '%{day}%'" for day in repeat_days) + ")) OR (recurrency = 'monthly'))"
                else:
                    command_for_recurrent += " OR (recurrency = 'monthly' AND days = ?) OR (recurrency = 'weekly'))"
    
                existing_recurrent_tasks = db.execute(
                    command_for_recurrent,
                    session["user_id"],
                    task_id,
                    start_time,
                    start_time,
                    end_time,
                    end_time,
                    start_time,
                    end_time,
                )
    
                conflicting_tasks = []
    
                for task in existing_recurrent_tasks:
                    conflicting_tasks.append(task)
    
                # CHECK FOR CONFLICTS WITH registered TASKS
                existing_registered_tasks = db.execute(
                    "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE user_id = ? AND id != ?",
                    session["user_id"],
                    task_id
                )
    
                for task in existing_registered_tasks:
                    start_time_object = datetime.strptime(task["start_time"], "%Y-%m-%d %H:%M")
                    end_time_object = datetime.strptime(task["end_time"], "%Y-%m-%d %H:%M")
    
                    start_hour_minute = start_time_object.strftime("%H:%M")
                    end_hour_minute = end_time_object.strftime("%H:%M")
    
                    if recurrence_type == "daily" or (recurrence_type == "weekly" and start_time_object.strftime("%A") in repeat_days) or (recurrence_type == "monthly" and str(start_time_object.day) in repeat_days):
                        if (start_hour_minute <= start_time <= end_hour_minute) or (start_hour_minute <= end_time <= end_hour_minute) or (start_time <= start_hour_minute <= end_time):
                            conflicting_tasks.append(task)
    
                if conflicting_tasks != [] and not force_conflict:
                    return render_template(
                        "index.html", 
                        conflict_tasks=conflicting_tasks, 
                        selected_date=date, 
                        selected_task={
                            "id": task_id,
                            "title": title,
                            "description": description,
                            "start_time": start_time,
                            "end_time": end_time,
                            "start_time_form": start_time,
                            "end_time_form": end_time
                        }, 
                        recurrent="True",
                    )
    
                db.execute(
                    "UPDATE recurrent_tasks SET title = ?, description = ?, start_time = ?, end_time = ?, recurrency = ?, days = ? WHERE id = ? AND user_id = ?",
                    title,
                    description,
                    start_time,
                    end_time,
                    recurrence_type,
                    " ".join(repeat_days),
                    task_id,
                    session["user_id"]
                )

            else:
                return redirect(url_for("recurring_tasks", error="Invalid table"))

        else:
            return apology("Invalid action", 400)

        return redirect("/")

@app.route("/new_task", methods=["GET", "POST"])
@login_required
def new_task():
    """Show the new task page or create a new task."""

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        force_conflict = request.form.get("force_conflict") == "1"

        task_type = request.form.get("task_type")
        if task_type == "common":
            if not title:
                return redirect(url_for("new_task", error="must provide title"))

            if not start_time or not end_time:
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
                return redirect(url_for("new_task", error="Start time must be before end time"))

            conflict_tasks = []

            search_existing_registered_tasks = db.execute(
                "SELECT * FROM registered_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?))",
                session["user_id"],
                start_time,
                start_time,
                end_time,
                end_time,
                start_time,
                end_time,
            )
        
            search_existing_recurrent_tasks = db.execute(
                "SELECT * FROM recurrent_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND (recurrency = 'daily' OR (recurrency = 'weekly' AND days LIKE ?) OR (recurrency = 'monthly' AND days LIKE ?))",
                session["user_id"],
                start_time.strftime("%H:%M"),
                start_time.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
                start_time.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
                f"%{start_time.strftime('%A')}%",
                f"%{start_time.strftime('%d')}%",
            )

            conflict_tasks += search_existing_registered_tasks + search_existing_recurrent_tasks
        
            if (search_existing_registered_tasks or search_existing_recurrent_tasks) and not force_conflict:
                return render_template(
                    "new_task.html",
                    conflict_tasks=conflict_tasks,
                    pending_task={
                        "task_type": "common",
                        "title": title,
                        "description": description,
                        "start_time": start_time.isoformat(timespec="minutes"),
                        "end_time": end_time.isoformat(timespec="minutes")
                    }
                )

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

            return redirect("new_task")
        
        elif task_type == "recurring":
            recurrence_type = request.form.get("repeat_interval")

            if recurrence_type == "weekly":
                repeat_days = request.form.getlist("repeat_days_week")
                for day in repeat_days:
                    if day not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                        return apology("Not a valid day of the week")
                    
            elif recurrence_type == "monthly":
                repeat_days = request.form.getlist("repeat_days_month")
                if repeat_days[0] not in [i for i in range(1, 32)]:
                    return apology("Not a valid day of the month")
    
            elif recurrence_type == "daily":
                repeat_days = []
            else:
                return render_template("new_task", error="Invalid recurrence type")
    
            if not title:
                return render_template("new_task", error="must provide title")
    
            if not start_time or not end_time:
                return render_template("new_task", error="must provide start and end time")
    
            time_pattern = r"^([0-1][0-9]|[2][0-3]):[0-5][0-9]$"
    
            if not re.match(time_pattern, start_time):
                return render_template("new_task", error="Invalid start time format")
    
            if not re.match(time_pattern, end_time):
                return render_template("new_task", error="Invalid end time format")
    
            if start_time >= end_time:
                return render_template("new_task", error="Start time must be before end time")
    
            if recurrence_type not in ["daily", "weekly", "monthly"]:
                return render_template("new_task", error="Invalid recurrence type")
    
            if recurrence_type == "weekly" and not repeat_days:
                return render_template("new_task", error="Must select at least one day for weekly recurrence")
    
            if recurrence_type == "monthly" and (not repeat_days or not all(day.isdigit() and 1 <= int(day) <= 31 for day in repeat_days)):
                return render_template("new_task", error="Must select valid days for monthly recurrence")
    
            # CHECK FOR CONFLICTS WITH OTHER recurrent TASKS
            command_for_recurrent = "SELECT * FROM recurrent_tasks WHERE user_id = ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND (recurrency = 'daily'"
    
            if recurrence_type == "daily":
                command_for_recurrent += ")"
            elif recurrence_type == "weekly":
                command_for_recurrent += " OR (recurrency = 'weekly' AND (" + " OR ".join(f"days LIKE '%{day}%'" for day in repeat_days) + ")) OR (recurrency = 'monthly'))"
            else:
                command_for_recurrent += f" OR (recurrency = 'monthly' AND days = [{repeat_days[0]}]) OR (recurrency = 'weekly'))"
    
            existing_recurrent_tasks = db.execute(
                command_for_recurrent,
                session["user_id"],
                start_time,
                start_time,
                end_time,
                end_time,
                start_time,
                end_time,
            )
    
            conflicting_tasks = []
    
            if existing_recurrent_tasks:
                conflicting_tasks += existing_recurrent_tasks
    
            # CHECK FOR CONFLICTS WITH registered TASKS
            existing_registered_tasks = db.execute(
                "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE user_id = ? AND start_time >= ?",
                session["user_id"],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
    
            for task in existing_registered_tasks:
                start_time_object = datetime.strptime(task["start_time"], "%Y-%m-%d %H:%M")
                end_time_object = datetime.strptime(task["end_time"], "%Y-%m-%d %H:%M")
    
                if recurrence_type == "daily" or (recurrence_type == "weekly" and start_time_object.strftime("%A") in repeat_days) or (recurrence_type == "monthly" and str(start_time_object.day) in repeat_days):
                    start_hour_minute = start_time_object.strftime("%H:%M")
                    end_hour_minute = end_time_object.strftime("%H:%M")
                    if (start_hour_minute <= start_time <= end_hour_minute) or (start_hour_minute <= end_time <= end_hour_minute) or (start_time <= start_hour_minute <= end_time):
                        conflicting_tasks.append(task)
    
            if conflicting_tasks and not force_conflict:
                return render_template(
                    "new_task.html",
                    conflict_tasks=conflicting_tasks,
                    pending_task={
                        "task_type": "recurring",
                        "title": title,
                        "description": description,
                        "start_time": start_time,
                        "end_time": end_time,
                        "repeat_interval": recurrence_type,
                        "repeat_days": repeat_days
                    }
                )
    
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
    
        return redirect("new_task")

    return render_template(
        "new_task.html",
    )

@app.route("/recurring_tasks", methods=["GET", "POST"])
@login_required
def recurring_tasks():
    recurring_tasks_rows = db.execute(
        "SELECT id, title, description, start_time, end_time, recurrency, days FROM recurrent_tasks WHERE user_id = ? ORDER BY start_time ASC"  ,
        session["user_id"],
    )

    for task in recurring_tasks_rows:
        task["days"] = [day.strip().title() for day in task["days"].split(" ") if day.strip()]

    if request.method == "GET":
        return render_template(
            "recurring_tasks.html",
            recurring_tasks=recurring_tasks_rows,
        )

    elif request.method == "POST":
        task_id = request.form.get("task_id")
        action = request.form.get("action")
        force_conflict = request.form.get("force_conflict") == "1"

        if action == "delete":
            
            db.execute(
                "DELETE FROM recurrent_tasks WHERE id = ? AND user_id = ?",
                task_id,
                session["user_id"]
            )

        elif action == "edit":
            title = request.form.get("title")
            description = request.form.get("description")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")
    
            if not title:
                return render_template("recurring_tasks.html", error="must provide title", recurring_tasks=recurring_tasks_rows)
    
            if not start_time or not end_time:
                return render_template("recurring_tasks.html", error="must provide start and end time", recurring_tasks=recurring_tasks_rows)

            time_pattern = r"^([0-1][0-9]|[2][0-3]):[0-5][0-9]$"
                        
            if not re.match(time_pattern, start_time):
                return render_template("recurring_tasks.html", error="Invalid start time format", recurring_tasks=recurring_tasks_rows)
    
            if not re.match(time_pattern, end_time):
                return render_template("recurring_tasks.html", error="Invalid end time format", recurring_tasks=recurring_tasks_rows)
    
            if start_time >= end_time:
                return render_template("recurring_tasks.html", error="Start time must be before end time", recurring_tasks=recurring_tasks_rows)
            
            recurrence_type = request.form.get("recurrency")
            repeat_days = db.execute("SELECT days FROM recurrent_tasks WHERE id = ? AND user_id = ?", task_id, session["user_id"])[0]["days"].split(" ")

            if recurrence_type == "weekly":
                repeat_days = request.form.getlist("repeat_days_week")
            elif recurrence_type == "monthly":
                repeat_days = request.form.getlist("repeat_days_month")
            elif recurrence_type == "daily":
                repeat_days = []
            else:
                return render_template("recurring_tasks.html", error="Invalid recurrence type", recurring_tasks=recurring_tasks_rows)

            if recurrence_type == "weekly" and not repeat_days:
                return render_template("recurring_tasks.html", error="Must select at least one day for weekly recurrence", recurring_tasks=recurring_tasks_rows)

            if recurrence_type == "monthly" and (not repeat_days or not all(day.isdigit() and 1 <= int(day) <= 31 for day in repeat_days)):
                return render_template("recurring_tasks.html", error="Must select valid days for monthly recurrence", recurring_tasks=recurring_tasks_rows)

            # CHECK FOR CONFLICTS WITH OTHER recurrent TASKS
            command_for_recurrent = "SELECT * FROM recurrent_tasks WHERE user_id = ? AND id != ? AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?) OR (start_time >= ? AND end_time <= ?)) AND (recurrency = 'daily'"

            if recurrence_type == "daily":
                command_for_recurrent += ")"
            elif recurrence_type == "weekly":
                command_for_recurrent += " OR (recurrency = 'weekly' AND (" + " OR ".join(f"days LIKE '%{day}%'" for day in repeat_days) + ")) OR (recurrency = 'monthly'))"
            else:
                command_for_recurrent += " OR (recurrency = 'monthly' AND days = ?) OR (recurrency = 'weekly'))"

            existing_recurrent_tasks = db.execute(
                command_for_recurrent,
                session["user_id"],
                task_id,
                start_time,
                start_time,
                end_time,
                end_time,
                start_time,
                end_time,
            )

            conflicting_tasks = []

            for task in existing_recurrent_tasks:
                conflicting_tasks.append(task)

            # CHECK FOR CONFLICTS WITH registered TASKS
            existing_registered_tasks = db.execute(
                "SELECT id, title, description, start_time, end_time FROM registered_tasks WHERE user_id = ? AND id != ? AND start_time >= ?",
                session["user_id"],
                task_id,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )

            for task in existing_registered_tasks:
                start_time_object = datetime.strptime(task["start_time"], "%Y-%m-%d %H:%M")
                end_time_object = datetime.strptime(task["end_time"], "%Y-%m-%d %H:%M")

                start_hour_minute = start_time_object.strftime("%H:%M")
                end_hour_minute = end_time_object.strftime("%H:%M")

                if recurrence_type == "daily" or (recurrence_type == "weekly" and start_time_object.strftime("%A") in repeat_days) or (recurrence_type == "monthly" and str(start_time_object.day) in repeat_days):
                    if (start_hour_minute <= start_time <= end_hour_minute) or (start_hour_minute <= end_time <= end_hour_minute) or (start_time <= start_hour_minute <= end_time):
                        conflicting_tasks.append(task)

            if conflicting_tasks != [] and not force_conflict:
                return render_template(
                    "recurring_tasks.html",
                    conflict_tasks=conflicting_tasks,
                    recurring_tasks=recurring_tasks_rows,
                    pending_task={
                        "task_id": task_id,
                        "title": title,
                        "description": description,
                        "start_time": start_time,
                        "end_time": end_time,
                        "recurrency": recurrence_type,
                        "repeat_days": repeat_days
                    }
                )

            db.execute(
                "UPDATE recurrent_tasks SET title = ?, description = ?, start_time = ?, end_time = ?, recurrency = ?, days = ? WHERE id = ? AND user_id = ?",
                title,
                description,
                start_time,
                end_time,
                recurrence_type,
                " ".join(repeat_days),
                task_id,
                session["user_id"]
            )

        return redirect("recurring_tasks")

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Show and update profile settings."""
    countries = load_countries()
    user = db.execute("SELECT username, country, hash FROM users WHERE id = ?", session["user_id"])

    if not user:
        return apology("User not found", 404)

    user = user[0]

    selected_country_name = ""
    for country_name in countries:
        country_code = countrycode(country_name, origin="country.name.en.regex", destination="iso3c")[0]
        if country_code == user["country"]:
            selected_country_name = country_name
            break

    if request.method == "GET":
        return render_template(
            "profile.html",
            username=user["username"],
            countries=countries,
            selected_country=selected_country_name,
        )

    action = request.form.get("action")

    if action == "username":
        new_username = request.form.get("username", "").strip()

        if not new_username:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="must provide username",
            )

        try:
            db.execute("UPDATE users SET username = ? WHERE id = ?", new_username, session["user_id"])
        except ValueError:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="Username already exists",
            )

        return render_template(
            "profile.html",
            username=new_username,
            countries=countries,
            selected_country=selected_country_name,
            success="Username updated successfully",
        )

    if action == "password":
        current_password = request.form.get("current_password")
        new_password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not current_password:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="must provide current password",
            )

        if not check_password_hash(user["hash"], current_password):
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="Current password is incorrect",
            )

        if not new_password:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="must provide password",
            )

        if not confirmation:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="must confirm your password",
            )

        if new_password != confirmation:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="Passwords don't match",
            )

        db.execute(
            "UPDATE users SET hash = ? WHERE id = ?",
            generate_password_hash(new_password),
            session["user_id"],
        )

        return render_template(
            "profile.html",
            username=user["username"],
            countries=countries,
            selected_country=selected_country_name,
            success="Password updated successfully",
        )

    if action == "country":
        country_name = request.form.get("country")

        if not country_name:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="must provide the country",
            )

        if country_name not in countries:
            return render_template(
                "profile.html",
                username=user["username"],
                countries=countries,
                selected_country=selected_country_name,
                error="Invalid country name",
            )

        country_code = countrycode(country_name, origin="country.name.en.regex", destination="iso3c")[0]
        db.execute("UPDATE users SET country = ? WHERE id = ?", country_code, session["user_id"])

        return render_template(
            "profile.html",
            username=user["username"],
            countries=countries,
            selected_country=country_name,
            success="Country updated successfully",
        )

    return render_template(
        "profile.html",
        username=user["username"],
        countries=countries,
        selected_country=selected_country_name,
        error="Invalid action",
    )
