import sqlite3


DATABASE = "lab.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def init_db():
    connection = get_connection()
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

    cursor.execute("""
        INSERT OR IGNORE INTO users
            (id, username, password, role, reset_token)
        VALUES
            (
                1,
                'alice',
                'alice123',
                'user',
                'RST-ALICE-2026'
            ),
            (
                2,
                'bob',
                'bob123',
                'user',
                'RST-BOB-2026'
            ),
            (
                3,
                'admin',
                'ADMIN_EXTERNAL',
                'admin',
                'RST-ADMIN-2026-7f91'
            )
    """)

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

    connection.commit()
    connection.close()


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

    if location:
        # Intentionally vulnerable for the lab.
        sql += f" AND location LIKE '%{location}%'"

    if min_price is not None:
        sql += " AND price >= ?"

    if max_price is not None:
        sql += " AND price <= ?"

    if guests is not None:
        sql += " AND guests >= ?"

    parameters = []

    if min_price is not None:
        parameters.append(min_price)

    if max_price is not None:
        parameters.append(max_price)

    if guests is not None:
        parameters.append(guests)

    cursor.execute(sql, parameters)

    results = cursor.fetchall()

    connection.close()

    return results

def get_user_by_credentials(username, password):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, username, role
        FROM users
        WHERE username = ? AND password = ?
        """,
        (username, password)
    )

    user = cursor.fetchone()

    connection.close()

    return user


def get_user_by_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, username, role, reset_token
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    connection.close()

    return user

def get_user_profile(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, username, role, reset_token
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    connection.close()

    return user

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

def update_password_with_token(reset_token, new_password):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE users
        SET password = ?
        WHERE reset_token = ?
        """,
        (new_password, reset_token)
    )

    changed = cursor.rowcount

    connection.commit()
    connection.close()

    return changed

def get_user_by_reset_token(reset_token):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, username, role
        FROM users
        WHERE reset_token = ?
        """,
        (reset_token,)
    )

    user = cursor.fetchone()

    connection.close()

    return user

def get_admin_reset_token():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT reset_token
        FROM users
        WHERE role = 'admin'
        LIMIT 1
    """)

    result = cursor.fetchone()

    connection.close()

    return result[0] if result else None