import sqlite3
import os
import csv
import io
from datetime import datetime
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

        site = row['site'] # Henley or Enfield (typically)

        if year not in summary:
            summary[year] = {
                'Total': {'checkins': 0, 'meals': 0, 'gifts': 0, 'referrals': 0, 'people': set()},
                'Henley': {'checkins': 0, 'meals': 0, 'gifts': 0, 'referrals': 0, 'people': set()},
                'Enfield': {'checkins': 0, 'meals': 0, 'gifts': 0, 'referrals': 0, 'people': set()}
            }

        # Helper to update stats
        def update_stats(stats, care_types, person):
            if care_types:
                if "Check-in" in care_types:
                    stats['checkins'] += 1
                if "Meals" in care_types:
                    stats['meals'] += 1
                if "Gifts" in care_types:
                    stats['gifts'] += 1
                if "Referral" in care_types:
                    stats['referrals'] += 1
            if person:
                normalized_person = person.strip().lower()
                stats['people'].add(normalized_person)

        care_types = row['care_types']
        person = row['person']

        # Update Total
        update_stats(summary[year]['Total'], care_types, person)

        # Update Site specific
        if site in ['Henley', 'Enfield']:
            update_stats(summary[year][site], care_types, person)

    # Convert to list for template
    final_summary = []
    for year in sorted(summary.keys(), reverse=True):
        for site in ['Henley', 'Enfield', 'Total']:
            data = summary[year][site]
            final_summary.append({
                'year': year,
                'site': site,
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

@app.route('/snapshot')
@login_required
def snapshot():
    db = get_db()
    cursor = db.execute('SELECT * FROM entries')
    entries = cursor.fetchall()

    people_data = {}

    for row in entries:
        person = row['person']
        if not person:
            continue

        # Normalize name: trim whitespace and capitalize words for display,
        # but use lowercase for key to handle duplicates
        normalized_key = person.strip().lower()

        care_types = row['care_types'] or ""
        date_str = row['date'] # YYYY-MM-DD
        site = row['site']

        if normalized_key not in people_data:
            # Use the first encountered name variant as the display name
            people_data[normalized_key] = {
                'name': person.strip(),
                'checkins': 0,
                'meals': 0,
                'gifts': 0,
                'referrals': 0,
                'last_date': date_str,
                'last_date_obj': datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.min,
                'last_site': site
            }

        # Update counts
        if "Check-in" in care_types:
            people_data[normalized_key]['checkins'] += 1
        if "Meals" in care_types:
            people_data[normalized_key]['meals'] += 1
        if "Gifts" in care_types:
            people_data[normalized_key]['gifts'] += 1
        if "Referral" in care_types:
            people_data[normalized_key]['referrals'] += 1

        # Update last date
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                if date_obj > people_data[normalized_key]['last_date_obj']:
                    people_data[normalized_key]['last_date_obj'] = date_obj
                    people_data[normalized_key]['last_date'] = date_str
                    people_data[normalized_key]['last_site'] = site
                    # Update display name to the one from the latest entry?
                    # Might be better if name changed slightly.
                    # But let's keep it simple.
            except ValueError:
                pass

    # Calculate overdue days
    today = datetime.now()
    final_data = []

    for key, data in people_data.items():
        days_since = 0
        if data['last_date_obj'] != datetime.min:
            delta = today - data['last_date_obj']
            days_since = delta.days

        # Format date for display: DD/MM/YYYY
        formatted_date = ""
        if data['last_date']:
             try:
                 dt = datetime.strptime(data['last_date'], '%Y-%m-%d')
                 formatted_date = dt.strftime('%d/%m/%Y')
             except ValueError:
                 formatted_date = data['last_date']

        final_data.append({
            'name': data['name'],
            'site': data['last_site'],
            'checkins': data['checkins'] if data['checkins'] > 0 else '',
            'meals': data['meals'] if data['meals'] > 0 else '',
            'gifts': data['gifts'] if data['gifts'] > 0 else '',
            'referrals': data['referrals'] if data['referrals'] > 0 else '',
            'last_date': formatted_date,
            'last_date_sort': data['last_date'], # Keep for potential sorting
            'overdue': days_since
        })

    # Sort by name
    final_data.sort(key=lambda x: x['name'].lower())

    return render_template('snapshot.html', people=final_data)

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
