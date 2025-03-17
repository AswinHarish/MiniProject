import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a secure key

# Helper function to connect to the database
def get_db_connection():
    conn = sqlite3.connect('SemReg.db')  
    conn.row_factory = sqlite3.Row  
    return conn

# Route: Home (Student Login Page)
@app.route('/')
def home():
    return render_template('login.html')

# Route: Student Login
@app.route('/login', methods=['POST'])
def login():
    admn_no = request.form.get('AdmnNo')
    adm_year = request.form.get('AdmYear')

    conn = get_db_connection()
    student = conn.execute('SELECT * FROM Students WHERE AdmnNo = ? AND AdmYear = ?', (admn_no, adm_year)).fetchone()
    conn.close()

    if student:
        session['AdmnNo'] = student['AdmnNo']
        flash("Login successful!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid Admission Number or Admission Year!", "danger")
        return redirect(url_for('home'))

# Route: Student Dashboard
@app.route('/dashboard')
def dashboard():
    if 'AdmnNo' in session:
        admn_no = session['AdmnNo']
        conn = get_db_connection()

        # Fetch student details, including their current semester
        student = conn.execute('SELECT * FROM Students WHERE AdmnNo = ?', (admn_no,)).fetchone()

        if not student:
            flash("Student not found!", "danger")
            return redirect(url_for('home'))

        student_semester = student['Sem']  # Fetch the student's current semester
        next_semester = student_semester + 1  # Determine next semester

        # Fetch registration status for the next semester
        registration_settings = conn.execute('SELECT IsOpen FROM RegistrationStatus WHERE Semester = ?', (next_semester,)).fetchone()

        conn.close()

        # Determine if registration should be displayed
        is_registration_open = registration_settings['IsOpen'] if registration_settings else 0

        return render_template('dashboard.html', student=student, is_registration_open=is_registration_open, sem=next_semester)
    
    else:
        flash("Please log in first!", "warning")
        return redirect(url_for('home'))




# Route: Admin Login
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM Admin WHERE email = ?', (email,)).fetchone()
        conn.close()

        if admin and password == admin['password']:  # Using plaintext passwords (not secure)
            session['admin_id'] = admin['id']
            session['role'] = admin['role']
            flash("Login successful!", "success")

            if admin['role'] == 'principal':
                return redirect(url_for('principal_dashboard'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid email or password!", "danger")

    return render_template('admin_login.html')

# Route: Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('admin_login'))

    db = get_db_connection()
    db.row_factory = sqlite3.Row  # Fetch results as dictionaries
    cursor = db.cursor()

    # Fetch admin details
    cursor.execute("SELECT name, role FROM Admin WHERE id = ?", (session['admin_id'],))
    admin = cursor.fetchone()

    if not admin:
        flash("Admin not found!", "danger")
        return redirect(url_for('admin_login'))

    admin_name = admin['name']
    admin_role = admin['role']  # This corresponds to DueDept in Dues table

    # Fetch dues with student details
    cursor.execute("""
        SELECT s.AdmnNo, s.Name AS student_name, s.Branch, s.Phone, 
               d.DueAmount, d.Remarks   
        FROM Dues d
        JOIN students s ON d.AdmnNo = s.AdmnNo
        WHERE d.DueDept = ?
        ORDER BY d.AdmnNo
    """, (admin_role,))

    dues = cursor.fetchall()
    db.close()

    return render_template('admin_dashboard.html', admin_name=admin_name, admin_role=admin_role, dues=dues)

# Route: Principal Dashboard (For Adding New Admins)
@app.route('/principal', methods=['GET', 'POST'])
def principal_dashboard():
    if 'role' not in session or session['role'] != 'principal':
        return redirect(url_for('admin_login'))  # Only the principal can access

    db = get_db_connection()
    cursor = db.cursor()

    # Fetch principal name using session ID
    cursor.execute("SELECT name FROM Admin WHERE id = ?", (session['admin_id'],))
    principal = cursor.fetchone()

    # Fetch all admins
    cursor.execute("SELECT id, name, email, role FROM Admin")  
    admins = cursor.fetchall()
    db.close()

    return render_template('principal_dashboard.html', principal_name=principal['name'], admins=admins)

# Route:  Add Admin
@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    if 'role' not in session or session['role'] != 'principal':
        return redirect(url_for('admin_login'))  # Only the principal can add admins

    db = get_db_connection()
    cursor = db.cursor()

    # Fetch principal name
    cursor.execute("SELECT name FROM Admin WHERE id = ?", (session['admin_id'],))
    principal = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        password = request.form['password']  # Storing plain text (should hash later)

        cursor.execute("INSERT INTO Admin (name, email, role, password) VALUES (?, ?, ?, ?)", 
                       (name, email, role, password))
        db.commit()
        db.close()

        return redirect(url_for('principal_dashboard'))  

    return render_template('add_admin.html', principal_name=principal['name'])

# Route: Remove Admin
@app.route('/remove_admin', methods=['GET', 'POST'])
def remove_admin():
    if 'role' not in session or session['role'] != 'principal':
        return redirect(url_for('admin_login'))  # Only the principal can remove admins

    db = get_db_connection()
    cursor = db.cursor()

    # Fetch principal name
    cursor.execute("SELECT name FROM Admin WHERE id = ?", (session['admin_id'],))
    principal = cursor.fetchone()

    # Fetch all admins except the principal
    cursor.execute("SELECT id, name, email, role FROM Admin WHERE role != 'principal'")
    admins = cursor.fetchall()
    db.close()

    return render_template('remove_admin.html', principal_name=principal['name'], admins=admins)

# Route to handle admin deletion
@app.route('/delete_admin/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    if 'role' not in session or session['role'] != 'principal':
        return redirect(url_for('admin_login'))  # Only the principal can delete admins

    db = get_db_connection()
    cursor = db.cursor()

    # Ensure the principal cannot delete themselves
    cursor.execute("SELECT role FROM Admin WHERE id = ?", (admin_id,))
    admin = cursor.fetchone()

    if admin and admin['role'] != 'principal':
        cursor.execute("DELETE FROM Admin WHERE id = ?", (admin_id,))
        db.commit()

    db.close()
    return redirect(url_for('remove_admin'))

# Route: Add Due
@app.route('/add_due', methods=['GET', 'POST'])
def add_due():
    if 'admin_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('admin_login'))
    
    db = get_db_connection()
    cursor = db.cursor()
    
    # Fetch admin role
    cursor.execute("SELECT * FROM Admin WHERE id = ?", (session['admin_id'],))
    admin = cursor.fetchone()
    
    if not admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    admin_role = admin['role']  # The department they belong to
    admin_name = admin['name']
    
    if request.method == 'POST':
        admn_no = request.form['admn_no']
        due_amount = request.form['due_amount']
        remarks = request.form['remarks']
        
        # Fetch student details
        cursor.execute("SELECT Name, Branch, Phone FROM Students WHERE AdmnNo = ?", (admn_no,))
        student = cursor.fetchone()

        if student:
            # Insert into Dues table
            cursor.execute(
                "INSERT INTO Dues (AdmnNo, Name, Branch, Phone, DueAmount, DueDept, Remarks) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (admn_no, student['Name'], student['Branch'], student['Phone'], due_amount, admin_role, remarks)
            )
            db.commit()
            flash("Due added successfully!", "success")
        else:
            flash("Student not found!", "danger")

        db.close()
        return redirect(url_for('add_due'))

    db.close()
    return render_template('add_due.html', admin_role=admin_role, admin_name=admin_name)

# Route: Clear Due
@app.route('/clear_due', methods=['GET', 'POST'])
def clear_due():
    if 'admin_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('admin_login'))

    db = get_db_connection()
    cursor = db.cursor()

    # Fetch admin details
    cursor.execute("SELECT name, role FROM Admin WHERE id = ?", (session['admin_id'],))
    admin = cursor.fetchone()

    if not admin:
        flash("Admin not found!", "danger")
        return redirect(url_for('admin_login'))
    
    admin_name = admin['name']
    admin_role = admin['role']  # This corresponds to DueDept in Dues table
    
    if request.method == 'POST':
        admn_no = request.form.get('admn_no')
        
        # Check if due exists and is added by the current admin role
        cursor.execute("SELECT * FROM Dues WHERE AdmnNo = ? AND DueDept = ?", (admn_no, admin_role))
        due = cursor.fetchone()
        
        if due:
            cursor.execute("DELETE FROM Dues WHERE AdmnNo = ? AND DueDept = ?", (admn_no, admin_role))
            db.commit()
            flash("Due cleared successfully!", "success")
        else:
            flash("No such due found or unauthorized action!", "danger")
        
    # Fetch all dues added by the logged-in admin
    cursor.execute("""
        SELECT s.AdmnNo, s.Name AS student_name, s.Branch, s.Phone, d.DueAmount, d.Remarks   
        FROM Dues d
        JOIN students s ON d.AdmnNo = s.AdmnNo
        WHERE d.DueDept = ?
        ORDER BY d.AdmnNo
    """, (admin_role,))
    
    dues = cursor.fetchall()
    db.close()
    
    return render_template('clear_due.html', admin_name=admin_name, admin_role=admin_role, dues=dues)

# route to update the registration status
@app.route('/update_registration', methods=['POST'])
def update_registration():
    if 'role' not in session or session['role'] != 'principal':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin_login'))

    semester = request.form.get('semester')
    is_open = 1 if 'is_open' in request.form else 0  # Checkbox handling

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO RegistrationStatus (Semester, IsOpen) 
        VALUES (?, ?) 
        ON CONFLICT(Semester) DO UPDATE SET IsOpen=excluded.IsOpen
    """, (semester, is_open))
    db.commit()
    db.close()

    flash(f"Registration for S{semester} {'enabled' if is_open else 'disabled'}!", "success")
    return redirect(url_for('principal_dashboard'))

# Route for registration
@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if 'AdmnNo' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('home'))

    admn_no = session['AdmnNo']
    conn = get_db_connection()

    # Fetch student details
    student = conn.execute("SELECT * FROM Students WHERE AdmnNo = ?", (admn_no,)).fetchone()
    
    if not student:
        flash("Student not found!", "danger")
        return redirect(url_for('home'))

    student = dict(student)

    # Fetch all departments from Admin table (excluding Principal and HOD)
    all_departments = conn.execute("""
        SELECT role AS DueDept, name AS StaffName, email AS StaffEmail 
        FROM Admin 
        WHERE role NOT IN ('principal', 'hod')
    """).fetchall()
    all_departments = [dict(row) for row in all_departments]

    # Fetch student's pending dues
    pending_dues = conn.execute("SELECT DueDept, DueAmount, Remarks FROM Dues WHERE AdmnNo = ?", (admn_no,)).fetchall()
    pending_dues = [dict(row) for row in pending_dues]

    due_depts = {due['DueDept'] for due in pending_dues}

    # Separate cleared dues departments
    no_dues_departments = [dept for dept in all_departments if dept['DueDept'] not in due_depts]

    # Join staff details to pending dues
    for due in pending_dues:
        staff = next((dept for dept in all_departments if dept['DueDept'] == due['DueDept']), {})
        due['StaffName'] = staff.get('StaffName', 'Unknown')
        due['StaffEmail'] = staff.get('StaffEmail', 'Unknown')

    # Check if student has already submitted registration
    completed_registration = conn.execute("SELECT 1 FROM CompletedRegistration WHERE AdmnNo = ?", (admn_no,)).fetchone()

    conn.close()

    return render_template(
        'registration.html', 
        student=student, 
        no_dues_departments=no_dues_departments, 
        pending_dues=pending_dues,
        registration_submitted=bool(completed_registration)
    )

# Submit registration
@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    if 'AdmnNo' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('home'))

    admn_no = session['AdmnNo']
    conn = get_db_connection()

    # Insert into CompletedRegistration if not already submitted
    conn.execute("INSERT INTO CompletedRegistration (AdmnNo) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM CompletedRegistration WHERE AdmnNo = ?)", (admn_no, admn_no))
    conn.commit()
    conn.close()

    flash("Registration request submitted! Waiting for HOD approval.", "info")
    return redirect(url_for('registration'))

# Route: Logout (For Both Students & Admins)
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
