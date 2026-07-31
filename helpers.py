import requests

from pathlib import Path

from flask import redirect, render_template, session
from functools import wraps


def load_countries():
    """Load country names from the provided text file."""
    countries_path = Path(__file__).parent / "countries.txt"
    if not countries_path.exists():
        return []

    countries = []
    with open(countries_path, encoding="utf-8") as file:
        for line in file:
            country = line.split("\t", 1)[0].strip()
            if country:
                countries.append(country)

    return countries


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)       

    return decorated_function