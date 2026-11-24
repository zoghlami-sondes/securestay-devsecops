from flask import Flask, request, render_template, session, redirect, url_for, abort, send_file
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path

import click
import secrets

from logging_config import correlation_id, log_event, setup_loggers, start_request
from database import (
    init_db,
    search_properties,
    get_user_by_credentials,
    get_user_by_id,
    get_property_by_id,
    create_booking,
    get_bookings_for_user,
    create_message,
    get_messages_for_user,
    get_user_by_username,
    get_all_users,
    get_all_properties,
    get_all_bookings,
    update_password_with_token,
    issue_reset_token
)

import os

FILES_DIRECTORY = os.path.join(
    os.path.dirname(__file__),
    "files"
)

class SecureStayApp(Flask):
    def log_exception(self, exc_info):
        # Exception messages and the default Flask request path may contain raw input.
        log_event(app_logger, "INTERNAL_ERROR", status=500)


app = SecureStayApp(__name__)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(32)

access_logger, auth_logger, app_logger = setup_loggers()
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

@app.route("/")
def index():
    return render_template("index.html")


class NonFinitePrice(ValueError):
    pass


def parse_optional_price(raw_price):
    if raw_price is None or raw_price == "":
        return None

    price = Decimal(raw_price)
    if not price.is_finite():
        event = "PRICE_NAN_REJECTED" if price.is_nan() else "PRICE_NONFINITE_REJECTED"
        raise NonFinitePrice(event)

    # SQLite binds REAL values as floats, which have a smaller range than Decimal.
    sqlite_price = float(price)
    if not isfinite(sqlite_price):
        raise ValueError("Price exceeds SQLite's numeric range")

    return sqlite_price


@app.route("/search")
def search():
    location = request.args.get("location", "")

    min_price_raw = request.args.get("min_price")
    max_price_raw = request.args.get("max_price")
    guests_raw = request.args.get("guests")

    try:
        min_price = parse_optional_price(min_price_raw)
        max_price = parse_optional_price(max_price_raw)
        guests = int(guests_raw) if guests_raw else None
    except NonFinitePrice as error:
        log_event(app_logger, error.args[0], status=400, count=True)
        return "Invalid search parameters", 400
    except (InvalidOperation, ValueError):
        return "Invalid search parameters", 400

    results = search_properties(
        location=location,
        min_price=min_price,
        max_price=max_price,
        guests=guests
    )

    return render_template(
        "search.html",
        location=location,
        min_price=min_price,
        max_price=max_price,
        guests=guests,
        results=results
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        user = get_user_by_credentials(username, password)

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[2]

            log_event(auth_logger, "LOGIN_SUCCESS")

            return redirect(url_for("profile"))

        log_event(auth_logger, "LOGIN_FAILURE", count=True)

        return render_template(
            "login.html",
            error="Invalid credentials."
        )

    return render_template("login.html")

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return profile_by_id(session["user_id"])

@app.route("/profile/<int:user_id>")
def profile_by_id(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    viewer = get_user_by_id(session["user_id"])
    if viewer is None or (viewer[0] != user_id and viewer[2] != "admin"):
        log_event(auth_logger, "PROFILE_ACCESS_DENIED", status=403, count=True)
        abort(403)

    user = viewer if viewer[0] == user_id else get_user_by_id(user_id)
    if user is None:
        abort(404)

    return render_template(
        "profile.html",
        user=user
    )

@app.route("/logout")
def logout():
    log_event(auth_logger, "LOGOUT")

    session.clear()

    return redirect(url_for("index"))

@app.route("/property/<int:property_id>")
def property_details(property_id):
    property_data = get_property_by_id(property_id)

    if not property_data:
        return "Property not found", 404

    return render_template(
        "property.html",
        property=property_data
    )

@app.route("/property/<int:property_id>/book", methods=["POST"])
def book_property(property_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    property_data = get_property_by_id(property_id)

    if not property_data:
        return "Property not found", 404

    create_booking(
        session["user_id"],
        property_id
    )

    log_event(app_logger, "BOOKING_CREATED")

    return redirect(url_for("bookings"))

@app.route("/bookings")
def bookings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    bookings = get_bookings_for_user(
        session["user_id"]
    )

    return render_template(
        "bookings.html",
        bookings=bookings
    )

@app.route("/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("login"))

    messages = get_messages_for_user(
        session["user_id"]
    )

    return render_template(
        "messages.html",
        messages=messages
    )

@app.route("/messages/send", methods=["GET", "POST"])
def send_message():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        recipient_username = request.form.get(
            "recipient",
            ""
        )
        content = request.form.get(
            "content",
            ""
        )

        recipient = get_user_by_username(
            recipient_username
        )

        if not recipient:
            return render_template(
                "send_message.html",
                error="User not found."
            )

        create_message(
            session["user_id"],
            recipient[0],
            content
        )

        log_event(app_logger, "MESSAGE_SENT")

        return redirect(url_for("messages"))

    return render_template("send_message.html")

@app.route("/download")
def download_file():
    filename = request.args.get("file", "")

    log_event(app_logger, "FILE_DOWNLOAD")

    root = Path(FILES_DIRECTORY).resolve()
    if not filename or any(character in filename for character in ("\\", ":", "\0")):
        abort(404)

    requested = Path(filename)
    if requested.is_absolute() or ".." in requested.parts:
        abort(404)

    try:
        file_path = (root / requested).resolve()
    except (OSError, RuntimeError, ValueError):
        abort(404)

    if not file_path.is_relative_to(root) or not file_path.is_file():
        abort(404)

    return send_file(
        file_path,
        as_attachment=True
    )

@app.cli.command("issue-reset-token")
@click.argument("username")
def issue_reset_token_command(username):
    """Issue a password reset token for an existing account."""
    token = issue_reset_token(username)
    if token is None:
        raise click.ClickException("User not found.")

    click.echo(token)


@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        log_event(app_logger, "ADMIN_ACCESS_UNAUTHENTICATED", status=302)

        return redirect(url_for("login"))

    if session.get("role") != "admin":
        log_event(app_logger, "ADMIN_ACCESS_DENIED", status=403, count=True)

        return "Forbidden", 403

    log_event(app_logger, "ADMIN_ACCESS_GRANTED")

    users = get_all_users()
    properties = get_all_properties()
    bookings = get_all_bookings()

    return render_template(
        "admin.html",
        users=users,
        properties=properties,
        bookings=bookings
    )

app.before_request(start_request)


@app.after_request
def log_request(response):
    response.headers["X-Correlation-ID"] = correlation_id()
    log_event(access_logger, "HTTP_REQUEST", status=response.status_code)
    return response


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        reset_token = request.form.get("token", "")
        new_password = request.form.get("password", "")

        if not new_password or not update_password_with_token(reset_token, new_password):
            return render_template(
                "reset_password.html",
                error="Invalid or expired token, or missing new password."
            ), 400

        return redirect(url_for("login"))

    return render_template("reset_password.html")

init_db(ADMIN_PASSWORD)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)