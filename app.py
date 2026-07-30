from countrycode import countrycode
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, load_countries

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
def index():
    """Show the home page"""
    if session["user_id"] not in session:
        return redirect("/login")

    return render_template("index.html")