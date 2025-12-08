import sqlite3
import os
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response
from functools import wraps

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_demo'  # Change this for production
DATABASE = 'data.db'
PASSWORD = 'admin'  # Hardcoded password for simplicity

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        # Person, Care Types, Date, Team Member, Notes, Plan, Site
        db.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person TEXT NOT NULL,
                care_types TEXT,
                date TEXT NOT NULL,
                team_member TEXT NOT NULL,
                notes TEXT,
                plan TEXT,
                site TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/breakdown')
def breakdown():
    db = get_db()
    cursor = db.execute('SELECT * FROM entries')
    entries = cursor.fetchall()

    summary = {}

    for row in entries:
        # Date format YYYY-MM-DD
        date_str = row['date']
        if not date_str or len(date_str) < 4:
            continue
        year = date_str[:4]

        if year not in summary:
            summary[year] = {
                'checkins': 0,
                'meals': 0,
                'gifts': 0,
                'referrals': 0,
                'people': set()
            }

        care_types = row['care_types']
        if care_types:
            if "Check-in" in care_types:
                summary[year]['checkins'] += 1
            if "Meals" in care_types:
                summary[year]['meals'] += 1
            if "Gifts" in care_types:
                summary[year]['gifts'] += 1
            if "Referral" in care_types:
                summary[year]['referrals'] += 1

        person = row['person']
        if person:
            # Normalize person name
            normalized_person = person.strip().lower()
            summary[year]['people'].add(normalized_person)

    # Convert sets to counts and sort by year descending
    final_summary = []
    for year in sorted(summary.keys(), reverse=True):
        data = summary[year]
        final_summary.append({
            'year': year,
            'checkins': data['checkins'],
            'meals': data['meals'],
            'gifts': data['gifts'],
            'referrals': data['referrals'],
            'people_count': len(data['people'])
        })

    return render_template('breakdown.html', summary=final_summary)

@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        person = request.form['person']
        # Handle multiple checkboxes for Care Types
        care_types = request.form.getlist('care_types')
        care_types_str = ", ".join(care_types)

        date = request.form['date']
        team_member = request.form['team_member']
        notes = request.form['notes']
        plan = request.form['plan']
        site = request.form['site']

        db = get_db()
        db.execute('''
            INSERT INTO entries (person, care_types, date, team_member, notes, plan, site)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (person, care_types_str, date, team_member, notes, plan, site))
        db.commit()

        flash('Entry submitted successfully!', 'success')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash('Invalid password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/api/entries')
@login_required
def get_entries():
    db = get_db()
    cursor = db.execute('SELECT * FROM entries ORDER BY date DESC')
    entries = cursor.fetchall()

    # Convert row objects to dictionary
    entries_list = []
    for row in entries:
        entries_list.append({
            'id': row['id'],
            'person': row['person'],
            'care_types': row['care_types'],
            'date': row['date'],
            'team_member': row['team_member'],
            'notes': row['notes'],
            'plan': row['plan'],
            'site': row['site'],
            'created_at': row['created_at']
        })

    return jsonify({'data': entries_list})

@app.route('/admin/export')
@login_required
def export_csv():
    db = get_db()
    cursor = db.execute('SELECT * FROM entries ORDER BY date DESC')
    entries = cursor.fetchall()

    si = io.StringIO()
    cw = csv.writer(si)
    # Write header
    cw.writerow(['ID', 'Person', 'Care Types', 'Date', 'Team Member', 'Notes', 'Plan', 'Site', 'Created At'])

    # Write data
    for row in entries:
        cw.writerow([row['id'], row['person'], row['care_types'], row['date'], row['team_member'], row['notes'], row['plan'], row['site'], row['created_at']])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=entries.csv"
    output.headers["Content-type"] = "text/csv"
    return output
@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_entry(id):
    db = get_db()
    db.execute('DELETE FROM entries WHERE id = ?', (id,))
    db.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, port=5000)
