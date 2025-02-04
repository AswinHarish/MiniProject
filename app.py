import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Helper function to interact with the database
def get_db_connection():
    conn = sqlite3.connect('SemReg.db')  # Adjust the path if needed
    conn.row_factory = sqlite3.Row  # This allows access to columns by name
    return conn

# Route: Home
@app.route('/')
def home():
    return render_template('login.html')

# Route: Login
@app.route('/login', methods=['POST'])
def login():
    # Retrieve the AdmnNo and AdmYear from the form
    admn_no = request.form.get('AdmnNo')
    adm_year = request.form.get('AdmYear')

    # Check database for student
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM Students WHERE AdmnNo = ? AND AdmYear = ?', (admn_no, adm_year)).fetchone()
    conn.close()

    if student:
        session['AdmnNo'] = student['AdmnNo']  # Store AdmnNo in the session
        flash("Login successful!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid Admission Number or Admission Year!", "danger")
        return redirect(url_for('home'))

# Route: Dashboard (After Login)
@app.route('/dashboard')
def dashboard():
    if 'AdmnNo' in session:
        admn_no = session['AdmnNo']
        conn = get_db_connection()
        student = conn.execute('SELECT * FROM Students WHERE AdmnNo = ?', (admn_no,)).fetchone()
        conn.close()
        return render_template('dashboard.html', student=student)
    else:
        flash("Please log in first!", "warning")
        return redirect(url_for('home'))

# Route: Logout
@app.route('/logout')
def logout():
    session.pop('AdmnNo', None)
    flash("Logged out successfully!", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
