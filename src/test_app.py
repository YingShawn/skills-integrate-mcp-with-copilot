import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app


class ActivityPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "activities.db"
        database_path_patch = patch.object(app, "DATABASE_PATH", self.database_path)
        database_path_patch.start()
        self.addCleanup(database_path_patch.stop)
        app.initialize_database()

    def test_fresh_database_seeds_activities_and_signups_persist(self):
        initial_activities = app.get_activities()
        self.assertIn("Chess Club", initial_activities)
        self.assertEqual(
            initial_activities["Chess Club"]["participants"],
            ["michael@mergington.edu", "daniel@mergington.edu"],
        )

        app.signup_for_activity("Chess Club", "newstudent@mergington.edu")
        with patch.object(app, "SEED_FILE", self.database_path.parent / "missing.json"):
            app.initialize_database()

        persisted = app.get_activities()["Chess Club"]
        self.assertIn("newstudent@mergington.edu", persisted["participants"])
        with app.database_connection() as connection:
            status = connection.execute(
                """
                SELECT approval_status FROM signups
                WHERE activity_name = 'Chess Club'
                    AND email = 'newstudent@mergington.edu'
                """
            ).fetchone()["approval_status"]
        self.assertEqual(status, "approved")

    def test_duplicate_signup_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            app.signup_for_activity("Chess Club", "michael@mergington.edu")

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Student is already signed up")

    def test_full_activity_rejects_additional_signup(self):
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "UPDATE activities SET max_participants = 2 WHERE name = 'Chess Club'"
            )

        with self.assertRaises(HTTPException) as error:
            app.signup_for_activity("Chess Club", "newstudent@mergington.edu")

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Activity is full")

    def test_database_is_not_reseeded_after_it_has_data(self):
        with app.database_connection() as connection:
            connection.execute(
                "UPDATE activities SET description = 'Updated description' "
                "WHERE name = 'Chess Club'"
            )

        app.initialize_database()

        self.assertEqual(
            app.get_activities()["Chess Club"]["description"],
            "Updated description",
        )


if __name__ == "__main__":
    unittest.main()
