"""Standalone dev server: `python3 app_dev.py`, then open /PostCloseAnalysis.

Production runs as a blueprint inside the existing Walters Hospitality app; this
file exists only so the dashboard can be developed and tested on its own.
"""
import os

from flask import Flask, redirect

from postclose import register

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-a-secret")
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024
register(app)


@app.route("/")
def home():
    return redirect("/PostCloseAnalysis")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
