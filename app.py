# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_secret')

# MySQL config from .env
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'pet_adoption')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)


# ---------- Helper: login_required decorators ----------
from functools import wraps
def login_required(role='user'):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_type' not in session:
                return redirect(url_for('login'))
            if role == 'user' and session.get('user_type') != 'user':
                flash('Access denied', 'danger'); return redirect(url_for('index'))
            if role == 'owner' and session.get('user_type') != 'owner':
                flash('Access denied', 'danger'); return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ---------- Home & listing ----------
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.*, o.Name AS OwnerName FROM Pets p JOIN Owners o ON p.OwnerID = o.OwnerID")
    pets = cur.fetchall()
    cur.close()
    return render_template('index.html', pets=pets)


@app.route('/pet/<int:pet_id>')
def pet_detail(pet_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.*, o.Name AS OwnerName, o.OwnerID FROM Pets p JOIN Owners o ON p.OwnerID = o.OwnerID WHERE p.PetID=%s", (pet_id,))
    pet = cur.fetchone()
    cur.close()
    if not pet:
        flash('Pet not found', 'warning'); return redirect(url_for('pets'))
    return render_template('pet_detail.html', pet=pet)


# ---------- User registration/login ----------
@app.route('/register', methods=['GET','POST'])
def register():
    # Register as user
    if request.method == 'POST':
        name = request.form['name']; email = request.form['email']
        phone = request.form.get('phone'); address = request.form.get('address')
        password = request.form['password']
        hashed = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO Users (Name, Email, Phone, Address, Password) VALUES (%s,%s,%s,%s,%s)",
                        (name,email,phone,address,hashed))
            mysql.connection.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Error: email may already exist', 'danger')
        finally:
            cur.close()
    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():
    # Login can be user or owner: we ask for account type
    if request.method == 'POST':
        email = request.form['email']; password = request.form['password']; acc_type = request.form['acc_type']
        cur = mysql.connection.cursor()
        if acc_type == 'user':
            cur.execute("SELECT * FROM Users WHERE Email=%s", (email,))
        else:
            cur.execute("SELECT * FROM Owners WHERE Email=%s", (email,))
        account = cur.fetchone()
        cur.close()
        if account and check_password_hash(account['Password'], password):
            # set session
            if acc_type == 'user':
                session['user_type'] = 'user'
                session['user_id'] = account['UserID']
                session['user_name'] = account['Name']
            else:
                session['user_type'] = 'owner'
                session['owner_id'] = account['OwnerID']
                session['user_name'] = account['Name']
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('index'))


# ---------- Owner registration ----------
@app.route('/owner_register', methods=['GET','POST'])
def owner_register():
    if request.method == 'POST':
        name = request.form['name']; email = request.form['email']; contact = request.form.get('contact')
        address = request.form.get('address'); password = request.form['password']
        hashed = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO Owners (Name, Email, Contact, Address, Password) VALUES (%s,%s,%s,%s,%s)",
                        (name,email,contact,address,hashed))
            mysql.connection.commit()
            flash('Owner registered. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception:
            mysql.connection.rollback(); flash('Error: email may already exist', 'danger')
        finally:
            cur.close()
    return render_template('owner_register.html')


# ---------- Owner dashboard + Pet CRUD ----------
@app.route('/owner/dashboard')
@login_required(role='owner')
def owner_dashboard():
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Pets WHERE OwnerID=%s", (owner_id,))
    pets = cur.fetchall()
    cur.close()
    return render_template('owner_dashboard.html', pets=pets)


@app.route('/owner/pet/add', methods=['GET','POST'])
@login_required(role='owner')
def owner_add_pet():
    if request.method == 'POST':
        owner_id = session.get('owner_id')
        name = request.form.get('name'); breed = request.form.get('breed'); ptype = request.form.get('type')
        age = request.form.get('age') or None; gender = request.form.get('gender'); color = request.form.get('color')
        size = request.form.get('size'); forsale = 1 if request.form.get('forsale') else 0
        forgroom = 1 if request.form.get('forgroom') else 0; desc = request.form.get('description')
        imageurl = request.form.get('imageurl')
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO Pets (OwnerID, Name, Breed, Type, Age, Gender, Color, Size, ForSale, ForGrooming, Description, ImageURL)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (owner_id, name, breed, ptype, age, gender, color, size, forsale, forgroom, desc, imageurl))
        mysql.connection.commit(); cur.close()
        flash('Pet added', 'success'); return redirect(url_for('owner_dashboard'))
    return render_template('owner_add_pet.html')


@app.route('/owner/pet/edit/<int:pet_id>', methods=['GET','POST'])
@login_required(role='owner')
def owner_edit_pet(pet_id):
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Pets WHERE PetID=%s AND OwnerID=%s", (pet_id, owner_id))
    pet = cur.fetchone()
    if not pet:
        cur.close(); flash('Pet not found or not yours', 'danger'); return redirect(url_for('owner_dashboard'))
    if request.method == 'POST':
        name = request.form.get('name'); breed = request.form.get('breed'); ptype = request.form.get('type')
        age = request.form.get('age') or None; gender = request.form.get('gender'); color = request.form.get('color')
        size = request.form.get('size'); forsale = 1 if request.form.get('forsale') else 0
        forgroom = 1 if request.form.get('forgroom') else 0; desc = request.form.get('description')
        imageurl = request.form.get('imageurl')
        cur.execute("""UPDATE Pets SET Name=%s, Breed=%s, Type=%s, Age=%s, Gender=%s, Color=%s, Size=%s,
                       ForSale=%s, ForGrooming=%s, Description=%s, ImageURL=%s WHERE PetID=%s""",
                    (name,breed,ptype,age,gender,color,size,forsale,forgroom,desc,imageurl,pet_id))
        mysql.connection.commit(); cur.close()
        flash('Pet updated', 'success'); return redirect(url_for('owner_dashboard'))
    cur.close()
    return render_template('owner_edit_pet.html', pet=pet)


@app.route('/owner/pet/delete/<int:pet_id>', methods=['POST'])
@login_required(role='owner')
def owner_delete_pet(pet_id):
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM Pets WHERE PetID=%s AND OwnerID=%s", (pet_id, owner_id))
    mysql.connection.commit(); cur.close()
    flash('Pet deleted', 'info'); return redirect(url_for('owner_dashboard'))


# ---------- Adoption requests ----------
@app.route('/adopt/<int:pet_id>', methods=['GET','POST'])
@login_required(role='user')
def adopt(pet_id):
    # show form and create request
    if request.method == 'POST':
        user_id = session.get('user_id'); message = request.form.get('message')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO AdoptionRequests (UserID, PetID, Message, Status) VALUES (%s,%s,%s,%s)",
                    (user_id, pet_id, message, 'Pending'))
        mysql.connection.commit(); cur.close()
        flash('Adoption request sent', 'success'); return redirect(url_for('my_requests'))
    # GET: show pet info
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Pets WHERE PetID=%s", (pet_id,))
    pet = cur.fetchone(); cur.close()
    if not pet: flash('Pet not found', 'warning'); return redirect(url_for('index'))
    return render_template('adopt.html', pet=pet)


@app.route('/my_requests')
@login_required(role='user')
def my_requests():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT r.*, 
                   p.Name AS PetName, 
                   p.ImageURL AS PetImage,
                   p.Breed AS PetBreed,
                   o.Name AS OwnerName,
                   o.Contact AS OwnerContact
                   FROM AdoptionRequests r
                   JOIN Pets p ON r.PetID = p.PetID
                   JOIN Owners o ON p.OwnerID = o.OwnerID
                   WHERE r.UserID=%s 
                   ORDER BY r.CreatedAt DESC""", (user_id,))
    requests = cur.fetchall(); cur.close()
    return render_template('my_requests.html', requests=requests)


@app.route('/owner/requests')
@login_required(role='owner')
def owner_requests():
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT r.*, p.Name AS PetName, u.Name AS UserName, u.Email AS UserEmail
                   FROM AdoptionRequests r
                   JOIN Pets p ON r.PetID = p.PetID
                   JOIN Users u ON r.UserID = u.UserID
                   WHERE p.OwnerID=%s ORDER BY r.CreatedAt DESC""", (owner_id,))
    requests = cur.fetchall(); cur.close()
    return render_template('owner_requests.html', requests=requests)


@app.route('/owner/request/decide/<int:req_id>', methods=['POST'])
@login_required(role='owner')
def owner_decide_request(req_id):
    decision = request.form.get('decision')  # 'Approve' or 'Reject'
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    # verify owner actually owns pet for this request
    cur.execute("""SELECT r.ReqID, r.PetID, p.OwnerID, r.UserID FROM AdoptionRequests r JOIN Pets p ON r.PetID=p.PetID WHERE r.ReqID=%s""", (req_id,))
    row = cur.fetchone()
    if not row or row['OwnerID'] != owner_id:
        cur.close(); flash('Request not found', 'danger'); return redirect(url_for('owner_requests'))
    if decision == 'Approve':
        cur.execute("UPDATE AdoptionRequests SET Status='Approved' WHERE ReqID=%s", (req_id,))
        # create entry in AdoptionHistory (no payment yet)
        cur.execute("INSERT INTO AdoptionHistory (UserID, PetID, OwnerID) VALUES (%s,%s,%s)", (row['UserID'], row['PetID'], owner_id))
        mysql.connection.commit()
        flash('Request approved', 'success')
    else:
        cur.execute("UPDATE AdoptionRequests SET Status='Rejected' WHERE ReqID=%s", (req_id,))
        mysql.connection.commit(); flash('Request rejected', 'info')
    cur.close()
    return redirect(url_for('owner_requests'))


# ---------- Payments (simple) ----------
@app.route('/payment/<int:req_id>', methods=['GET','POST'])
@login_required(role='user')
def make_payment(req_id):
    # Show payment form and store
    if request.method == 'POST':
        mode = request.form.get('mode'); amount = request.form.get('amount') or 0
        user_id = session.get('user_id')
        # find request info & owner
        cur = mysql.connection.cursor()
        cur.execute("""SELECT r.ReqID, r.UserID, p.OwnerID FROM AdoptionRequests r JOIN Pets p ON r.PetID=p.PetID WHERE r.ReqID=%s""", (req_id,))
        info = cur.fetchone()
        if not info or info['UserID'] != user_id:
            cur.close(); flash('Invalid request', 'danger'); return redirect(url_for('my_requests'))
        cur.execute("INSERT INTO Payments (ReqID, UserID, OwnerID, Mode, Amount) VALUES (%s,%s,%s,%s,%s)",
                    (req_id, user_id, info['OwnerID'], mode, amount))
        payment_id = cur.lastrowid
        # update AdoptionHistory to set PaymentID for the latest adoption of this pet and user
        cur.execute("""UPDATE AdoptionHistory SET PaymentID=%s WHERE UserID=%s AND PetID=
                       (SELECT PetID FROM AdoptionRequests WHERE ReqID=%s) ORDER BY Date DESC LIMIT 1""",
                    (payment_id, user_id, req_id))
        mysql.connection.commit(); cur.close()
        flash('Payment recorded', 'success'); return redirect(url_for('my_history'))
    # GET display
    return render_template('payment.html', req_id=req_id)


@app.route('/my_history')
@login_required(role='user')
def my_history():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT h.*, p.Name AS PetName, o.Name AS OwnerName, pay.Mode AS PaymentMode, pay.Amount
                   FROM AdoptionHistory h
                   JOIN Pets p ON h.PetID = p.PetID
                   JOIN Owners o ON h.OwnerID = o.OwnerID
                   LEFT JOIN Payments pay ON h.PaymentID = pay.PaymentID
                   WHERE h.UserID=%s ORDER BY h.Date DESC""", (user_id,))
    rows = cur.fetchall(); cur.close()
    return render_template('my_history.html', history=rows)


# ---------- simple search/filter (optional) ----------
@app.route('/search')
def search():
    q = request.args.get('q','')
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.*, o.Name AS OwnerName FROM Pets p JOIN Owners o ON p.OwnerID=o.OwnerID WHERE p.Name LIKE %s OR p.Breed LIKE %s", (f"%{q}%", f"%{q}%"))
    pets = cur.fetchall(); cur.close()
    return render_template('index.html', pets=pets)


if __name__ == '__main__':
    app.run(debug=True)