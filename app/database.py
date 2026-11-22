import hashlib
import secrets
import sqlite3
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash


DATABASE = "lab.db"
RESET_TOKEN_TTL = 30 * 60


def get_connection():
    return sqlite3.connect(DATABASE)


def init_db(admin_password):
    with closing(get_connection()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                reset_token TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL,
                owner_id INTEGER,
                brochure TEXT,
                guests INTEGER NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                property_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (property_id) REFERENCES properties(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users(id),
                FOREIGN KEY (recipient_id) REFERENCES users(id)
            )
        """)

        columns = {column[1] for column in cursor.execute("PRAGMA table_info(users)")}
        if "password_hashed" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hashed INTEGER NOT NULL DEFAULT 0")
        if "reset_token_expires_at" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expires_at INTEGER")
            cursor.execute("UPDATE users SET reset_token = NULL")

        cursor.executemany("""
            INSERT OR IGNORE INTO users (id, username, password, role)
            VALUES (?, ?, ?, ?)
        """, [
            (1, "alice", "alice123", "user"),
            (2, "bob", "bob123", "user"),
            (3, "admin", admin_password, "admin"),
        ])

        legacy_users = cursor.execute("""
            SELECT id, username, password, role FROM users WHERE password_hashed = 0
        """).fetchall()
        for user_id, username, password, role in legacy_users:
            if username == "admin" and role == "admin" and password == "ADMIN_EXTERNAL":
                password = admin_password

            cursor.execute("""
                UPDATE users SET password = ?, password_hashed = 1 WHERE id = ?
            """, (generate_password_hash(password), user_id))

        cursor.execute("""
            INSERT OR IGNORE INTO properties
                (id, title, location, description, price, owner_id, brochure, guests)
            VALUES
                (
                    1,
                    'Madrid Central Apartment',
                    'Madrid, Spain',
                    'Modern apartment in central Madrid.',
                    120,
                    1,
                    'madrid-brochure.txt',
                    2
                ),
                (
                    2,
                    'Barcelona Beach House',
                    'Barcelona, Spain',
                    'Beach house with sea views.',
                    180,
                    2,
                    'barcelona-brochure.txt',
                    6
                ),
                (
                    3,
                    'Lisbon Studio',
                    'Lisbon, Portugal',
                    'Cozy studio in the city center.',
                    95,
                    2,
                    'lisbon-brochure.txt',
                    2
                )
        """)


def search_properties(
    location="",
    min_price=None,
    max_price=None,
    guests=None
):
    connection = get_connection()
    cursor = connection.cursor()

    sql = """
        SELECT id, title, location, description, price, guests
        FROM properties
        WHERE 1=1
    """

    parameters = []

    if location:
        sql += " AND location LIKE ?"
        parameters.append(f"%{location}%")

    if min_price is not None:
        sql += " AND price >= ?"
        parameters.append(min_price)

    if max_price is not None:
        sql += " AND price <= ?"
        parameters.append(max_price)

    if guests is not None:
        sql += " AND guests >= ?"
        parameters.append(guests)

    cursor.execute(sql, parameters)

    results = cursor.fetchall()

    connection.close()

    return results

def get_user_by_credentials(username, password):
    with closing(get_connection()) as connection:
        user = connection.execute(
            "SELECT id, username, role, password FROM users WHERE username = ?",
            (username,)
        ).fetchone()

    if user and check_password_hash(user[3], password):
        return user[:3]

    return None


def get_user_by_id(user_id):
    with closing(get_connection()) as connection:
        return connection.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()


def get_property_by_id(property_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, title, location, description, price, owner_id, brochure
        FROM properties
        WHERE id = ?
        """,
        (property_id,)
    )

    property_data = cursor.fetchone()

    connection.close()

    return property_data

def create_booking(user_id, property_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO bookings (user_id, property_id, status)
        VALUES (?, ?, ?)
        """,
        (user_id, property_id, "confirmed")
    )

    booking_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return booking_id

def get_bookings_for_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            bookings.id,
            properties.title,
            properties.location,
            properties.price,
            bookings.status
        FROM bookings
        JOIN properties
            ON bookings.property_id = properties.id
        WHERE bookings.user_id = ?
        ORDER BY bookings.id DESC
        """,
        (user_id,)
    )

    bookings = cursor.fetchall()

    connection.close()

    return bookings

def create_message(sender_id, recipient_id, content):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO messages (sender_id, recipient_id, content)
        VALUES (?, ?, ?)
        """,
        (sender_id, recipient_id, content)
    )

    connection.commit()
    connection.close()


def get_messages_for_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            messages.id,
            users.username,
            messages.content
        FROM messages
        JOIN users
            ON messages.sender_id = users.id
        WHERE messages.recipient_id = ?
        ORDER BY messages.id DESC
        """,
        (user_id,)
    )

    messages = cursor.fetchall()

    connection.close()

    return messages


def get_user_by_username(username):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, username, role
        FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()

    connection.close()

    return user

def get_all_users():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, username, role
        FROM users
        ORDER BY id
    """)

    users = cursor.fetchall()

    connection.close()

    return users


def get_all_properties():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, title, location, price
        FROM properties
        ORDER BY id
    """)

    properties = cursor.fetchall()

    connection.close()

    return properties


def get_all_bookings():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            bookings.id,
            users.username,
            properties.title,
            bookings.status
        FROM bookings
        JOIN users
            ON bookings.user_id = users.id
        JOIN properties
            ON bookings.property_id = properties.id
        ORDER BY bookings.id DESC
    """)

    bookings = cursor.fetchall()

    connection.close()

    return bookings

def issue_reset_token(username):
    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    with closing(get_connection()) as connection, connection:
        result = connection.execute("""
            UPDATE users
            SET reset_token = ?, reset_token_expires_at = unixepoch() + ?
            WHERE username = ?
        """, (token_digest, RESET_TOKEN_TTL, username))

    return token if result.rowcount == 1 else None


def update_password_with_token(reset_token, new_password):
    if not reset_token or not new_password:
        return False

    token_digest = hashlib.sha256(reset_token.encode()).hexdigest()
    with closing(get_connection()) as connection, connection:
        eligible_user = connection.execute("""
            SELECT id FROM users
            WHERE reset_token = ? AND reset_token_expires_at > unixepoch()
        """, (token_digest,)).fetchone()

        if eligible_user is None:
            return False

        # Recheck the token in the write so concurrent requests can consume it only once.
        result = connection.execute("""
            UPDATE users
            SET password = ?, password_hashed = 1,
                reset_token = NULL, reset_token_expires_at = NULL
            WHERE id = ? AND reset_token = ? AND reset_token_expires_at > unixepoch()
        """, (generate_password_hash(new_password), eligible_user[0], token_digest))

    return result.rowcount == 1
