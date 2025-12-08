import unittest
import os
import sqlite3
import csv
import io

# We need to run the app in a separate process or use Flask's test client.
# Since app.py has `if __name__ == '__main__': app.run(...)`, we can import it.
from app import app, init_db, get_db

class TestExportCSV(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret'
        self.app = app.test_client()

        # Initialize a test database
        with app.app_context():
            init_db()
            db = get_db()
            # Clear existing data
            db.execute('DELETE FROM entries')
            # Insert sample data
            db.execute('''
                INSERT INTO entries (person, care_types, date, team_member, notes, plan, site)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('John Doe', 'Type A, Type B', '2023-10-27', 'Jane Smith', 'Test Notes', 'Test Plan', 'Henley'))
            db.commit()

    def login(self, password):
        return self.app.post('/login', data=dict(
            password=password
        ), follow_redirects=True)

    def test_export_csv(self):
        # First, try to access without login
        response = self.app.get('/admin/export', follow_redirects=True)
        # Should redirect to login
        self.assertIn(b'Login', response.data)

        # Login
        self.login('admin')

        # Request export
        response = self.app.get('/admin/export')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=entries.csv', response.headers['Content-Disposition'])

        # Parse CSV content
        content = response.data.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Check header
        self.assertEqual(rows[0], ['ID', 'Person', 'Care Types', 'Date', 'Team Member', 'Notes', 'Plan', 'Site', 'Created At'])

        # Check data row
        self.assertEqual(rows[1][1], 'John Doe')
        self.assertEqual(rows[1][2], 'Type A, Type B')
        self.assertEqual(rows[1][3], '2023-10-27')
        self.assertEqual(rows[1][4], 'Jane Smith')
        self.assertEqual(rows[1][5], 'Test Notes')
        self.assertEqual(rows[1][6], 'Test Plan')
        self.assertEqual(rows[1][7], 'Henley')

if __name__ == '__main__':
    unittest.main()
