import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from werkzeug.security import check_password_hash

import database
import logging_config


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary_directory.cleanup)
        directory = Path(temporary_directory.name)
        cls.enterClassContext(patch.object(database, "DATABASE", directory / "test.db"))
        cls.enterClassContext(patch.object(logging_config, "LOG_DIRECTORY", directory / "logs"))
        cls.enterClassContext(patch.dict(os.environ, {"ADMIN_PASSWORD": "bootstrap-test-password"}))
        with closing(database.get_connection()) as connection, connection:
            connection.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    reset_token TEXT
                );
                INSERT INTO users VALUES
                    (1, 'alice', 'existing-alice-password', 'user', 'legacy-token'),
                    (3, 'admin', 'ADMIN_EXTERNAL', 'admin', 'legacy-admin-token');
            """)

        from app import access_logger, app, app_logger, auth_logger

        for logger in (access_logger, app_logger, auth_logger):
            for handler in list(logger.handlers):
                cls.addClassCleanup(handler.close)
                cls.addClassCleanup(logger.removeHandler, handler)

        cls.app = app
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, username, password):
        return self.client.post("/login", data={"username": username, "password": password})

    def issue_token(self, username):
        result = self.app.test_cli_runner().invoke(args=["issue-reset-token", username])
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output.strip()

    def reset(self, token, password):
        return self.client.post("/reset-password", data={"token": token, "password": password})

    def test_search_binds_location_and_numeric_filters(self):
        response = self.client.get("/search", query_string={
            "location": "Madrid", "min_price": 100, "max_price": 130, "guests": 2
        })
        self.assertIn(b"Madrid Central Apartment", response.data)
        self.assertNotIn(b"Barcelona Beach House", response.data)
        self.assertEqual(database.search_properties(location="'"), [])
        self.assertEqual(database.search_properties(location="Location with ' and ?"), [])

    def test_search_rejects_invalid_price_bounds(self):
        invalid_prices = (
            "NaN", "nAn", "sNaN", "Infinity", "-Infinity", "+inf",
            "not-a-number", "12.3.4", " ", "1e9999", "-1e9999",
        )
        for field in ("min_price", "max_price"):
            for value in invalid_prices:
                with self.subTest(field=field, value=value):
                    response = self.client.get("/search", query_string={field: value})
                    self.assertEqual(response.status_code, 400)

    def test_search_filters_with_decimal_price_bounds(self):
        response = self.client.get("/search", query_string={
            "min_price": "95.01", "max_price": "179.99",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Madrid Central Apartment", response.data)
        self.assertNotIn(b"Lisbon Studio", response.data)
        self.assertNotIn(b"Barcelona Beach House", response.data)

    def test_search_treats_empty_price_bounds_as_unset(self):
        response = self.client.get("/search", query_string={
            "min_price": "", "max_price": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Lisbon Studio", response.data)
        self.assertIn(b"Barcelona Beach House", response.data)

    def test_download_is_confined_to_brochure_directory(self):
        response = self.client.get("/download", query_string={"file": "madrid-brochure.txt"})
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response.headers["Content-Disposition"])
        finally:
            response.close()

        for filename in ("../internal/support-notes.txt", "..\\internal\\support-notes.txt",
                         "/internal/support-notes.txt", "missing.txt", ""):
            with self.subTest(filename=filename):
                self.assertEqual(
                    self.client.get("/download", query_string={"file": filename}).status_code,
                    404,
                )

    def test_profile_checks_ownership_and_excludes_tokens(self):
        self.assertEqual(self.client.get("/profile/1").status_code, 302)
        self.assertEqual(self.login("alice", "existing-alice-password").status_code, 302)
        token = self.issue_token("alice")
        for path in ("/profile", "/profile/1"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"alice", response.data)
            self.assertNotIn(b"Password reset token", response.data)
            self.assertNotIn(token.encode(), response.data)
        self.assertEqual(self.client.get("/profile/2").status_code, 403)
        self.assertEqual(database.get_user_by_id(1), (1, "alice", "user"))

    def test_reset_tokens_expire_and_can_only_be_used_once(self):
        self.assertEqual(self.reset("legacy-token", "unused").status_code, 400)
        replaced = self.issue_token("bob")
        expired = self.issue_token("bob")
        self.assertNotEqual(replaced, expired)
        self.assertEqual(self.reset(replaced, "unused").status_code, 400)
        with closing(database.get_connection()) as connection, connection:
            stored_token = connection.execute(
                "SELECT reset_token FROM users WHERE username = 'bob'"
            ).fetchone()[0]
            self.assertEqual(stored_token, hashlib.sha256(expired.encode()).hexdigest())
            connection.execute("UPDATE users SET reset_token_expires_at = 0 WHERE username = 'bob'")
        self.assertEqual(self.reset(expired, "unused").status_code, 400)

        token = self.issue_token("bob")
        self.assertEqual(self.reset(token, "").status_code, 400)
        self.assertEqual(self.reset(token, "new-bob-password").status_code, 302)
        self.assertEqual(self.reset(token, "unused").status_code, 400)
        self.assertEqual(self.login("bob", "bob123").status_code, 200)
        self.assertEqual(self.login("bob", "new-bob-password").status_code, 302)
        with closing(database.get_connection()) as connection:
            password, token, expiry = connection.execute("""
                SELECT password, reset_token, reset_token_expires_at FROM users WHERE username = 'bob'
            """).fetchone()
        self.assertTrue(check_password_hash(password, "new-bob-password"))
        self.assertEqual((token, expiry), (None, None))

    def test_admin_reset_survives_database_initialization(self):
        self.assertEqual(self.client.get("/admin/support").status_code, 404)
        self.assertEqual(self.login("admin", "bootstrap-test-password").status_code, 302)
        self.assertEqual(self.client.get("/profile/1").status_code, 200)
        self.assertEqual(self.client.get("/profile/999").status_code, 404)
        token = self.issue_token("admin")
        self.assertEqual(self.reset(token, "new-admin-password").status_code, 302)
        database.init_db("bootstrap-test-password")
        self.assertEqual(self.login("admin", "bootstrap-test-password").status_code, 200)
        self.assertEqual(self.login("admin", "new-admin-password").status_code, 302)


if __name__ == "__main__":
    unittest.main()
