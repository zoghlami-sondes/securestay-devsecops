from flask import Flask, request, render_template, session, redirect, url_for, send_from_directory, send_file
from datetime import datetime
from logging_config import setup_loggers
from database import (
    init_db,
    search_properties,
    get_user_by_credentials,
    get_user_by_id,
    get_user_profile,
    get_property_by_id,
    create_booking,
    get_bookings_for_user,
    create_message,
    get_messages_for_user,
    get_user_by_username,
    create_booking,
    get_all_users,
    get_all_properties,
    get_all_bookings,
    update_password_with_token,
    get_user_by_reset_token,
    get_admin_reset_token
)

import os

FILES_DIRECTORY = os.path.join(
    os.path.dirname(__file__),
    "files"
)

app = Flask(__name__)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "SecureStay-Admin-Internal-2026"
)

SUPPORT_CODE = os.environ.get(
    "SUPPORT_CODE",
    "SS-SUPPORT-2026"
)

access_logger, auth_logger, app_logger = setup_loggers()
app.secret_key = "dev-secret-key"

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    location = request.args.get("location", "")

    min_price_raw = request.args.get("min_price")
    max_price_raw = request.args.get("max_price")
    guests_raw = request.args.get("guests")

    try:
        min_price = float(min_price_raw) if min_price_raw else None
        max_price = float(max_price_raw) if max_price_raw else None
        guests = int(guests_raw) if guests_raw else None
    except ValueError:
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

        source_ip = request.headers.get(
            "X-Lab-Source-IP",
            request.remote_addr
        )

        if username == "admin":
            if password == ADMIN_PASSWORD:
                user = get_user_by_id(3)
            else:
                user = None
        else:
            user = get_user_by_credentials(
                username,
                password
            )

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[2]

            auth_logger.info(
                f"{datetime.utcnow().isoformat()} "
                f"source_ip={source_ip} "
                f"event=LOGIN_SUCCESS "
                f"username={username}"
            )

            return redirect(url_for("profile"))

        auth_logger.info(
            f"{datetime.utcnow().isoformat()} "
            f"source_ip={source_ip} "
            f"event=LOGIN_FAILURE "
            f"username={username}"
        )

        return render_template(
            "login.html",
            error="Invalid credentials."
        )

    return render_template("login.html")

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    return render_template(
        "profile.html",
        user=user
    )

@app.route("/profile/<int:user_id>")
def profile_by_id(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_profile(user_id)

    return render_template(
        "profile.html",
        user=user
    )

@app.route("/logout")
def logout():
    source_ip = request.headers.get(
        "X-Lab-Source-IP",
        request.remote_addr
    )

    username = session.get("username", "unknown")

    auth_logger.info(
        f"{datetime.utcnow().isoformat()} "
        f"source_ip={source_ip} "
        f"event=LOGOUT "
        f"username={username}"
    )

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

    booking_id = create_booking(
        session["user_id"],
        property_id
    )

    app_logger.info(
        f"{datetime.utcnow().isoformat()} "
        f"source_ip={request.headers.get('X-Lab-Source-IP', request.remote_addr)} "
        f"event=BOOKING_CREATED "
        f"user_id={session['user_id']} "
        f"property_id={property_id} "
        f"booking_id={booking_id}"
    )

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

        app_logger.info(
            f"{datetime.utcnow().isoformat()} "
            f"source_ip={request.headers.get('X-Lab-Source-IP', request.remote_addr)} "
            f"event=MESSAGE_SENT "
            f"sender_id={session['user_id']} "
            f"recipient_id={recipient[0]}"
        )

        return redirect(url_for("messages"))

    return render_template("send_message.html")

@app.route("/download")
def download_file():
    filename = request.args.get("file", "")

    app_logger.info(
        f"{datetime.utcnow().isoformat()} "
        f"source_ip={request.headers.get('X-Lab-Source-IP', request.remote_addr)} "
        f"event=FILE_DOWNLOAD "
        f"filename={filename}"
    )

    file_path = os.path.join(FILES_DIRECTORY, filename)

    return send_file(
        file_path,
        as_attachment=True
    )

@app.route("/admin/support")
def admin_support():
    code = request.args.get("code", "")

    if code != SUPPORT_CODE:
        return "Forbidden", 403

    return render_template(
        "admin_support.html",
        reset_token=get_admin_reset_token()
    )

@app.route("/admin")
def admin_dashboard():
    source_ip = request.headers.get(
        "X-Lab-Source-IP",
        request.remote_addr
    )

    if "user_id" not in session:
        app_logger.info(
            f"{datetime.utcnow().isoformat()} "
            f"source_ip={source_ip} "
            f"event=ADMIN_ACCESS_UNAUTHENTICATED"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":
        app_logger.info(
            f"{datetime.utcnow().isoformat()} "
            f"source_ip={source_ip} "
            f"event=ADMIN_ACCESS_DENIED "
            f"user_id={session['user_id']}"
        )

        return "Forbidden", 403

    app_logger.info(
        f"{datetime.utcnow().isoformat()} "
        f"source_ip={source_ip} "
        f"event=ADMIN_ACCESS_GRANTED "
        f"user_id={session['user_id']}"
    )

    users = get_all_users()
    properties = get_all_properties()
    bookings = get_all_bookings()

    return render_template(
        "admin.html",
        users=users,
        properties=properties,
        bookings=bookings
    )

@app.after_request
def log_request(response):
    source_ip = request.headers.get(
        "X-Lab-Source-IP",
        request.remote_addr
    )

    timestamp = datetime.utcnow().isoformat()

    access_logger.info(
        f"{timestamp} "
        f"source_ip={source_ip} "
        f'method="{request.method}" '
        f'path="{request.full_path.rstrip("?")}" '
        f"status={response.status_code} "
        f"bytes={response.calculate_content_length() or 0}"
    )

    return response

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    global ADMIN_PASSWORD

    if request.method == "POST":
        reset_token = request.form.get("token", "")
        new_password = request.form.get("password", "")

        user = get_user_by_reset_token(reset_token)

        if not user:
            return render_template(
                "reset_password.html",
                error="Invalid reset token."
            )

        if user[2] == "admin":
            ADMIN_PASSWORD = new_password
        else:
            update_password_with_token(
                reset_token,
                new_password
            )

        return redirect(url_for("login"))

    return render_template("reset_password.html")

init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)