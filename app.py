# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import time
import uuid
from datetime import datetime

load_dotenv()

app = Flask(__name__, static_folder='templates/static', static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', 'dev_secret')

# MySQL config from .env
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'hero')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# File upload configuration
UPLOAD_FOLDER = os.path.join('templates', 'static', 'uploads', 'pets')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

mysql = MySQL(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Helper: login_required decorators ----------
from functools import wraps
def login_required(role='user'):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_type' not in session:
                flash('Please login first', 'warning')
                return redirect(url_for('login'))
            if role == 'user' and session.get('user_type') != 'user':
                flash('Access denied', 'danger')
                return redirect(url_for('index'))
            if role == 'owner' and session.get('user_type') != 'owner':
                flash('Access denied', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ---------- Home & listing ----------
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.*, o.Name AS OwnerName FROM Pets p JOIN Owners o ON p.OwnerID = o.OwnerID WHERE p.Status='available'")
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
        flash('Pet not found', 'warning')
        return redirect(url_for('index'))
    return render_template('pet_detail.html', pet=pet)

# ---------- User registration/login ----------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        password = request.form.get('password')
        hashed = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO Users (Name, Email, Phone, Address, Password) VALUES (%s,%s,%s,%s,%s)",
                        (name, email, phone, address, hashed))
            mysql.connection.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Email already registered', 'danger')
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        acc_type = request.form.get('acc_type')
        cur = mysql.connection.cursor()
        
        if acc_type == 'user':
            cur.execute("SELECT * FROM Users WHERE Email=%s", (email,))
        else:
            cur.execute("SELECT * FROM Owners WHERE Email=%s", (email,))
        
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user.get('Password'), password):
            session['user_type'] = acc_type
            session['user_id'] = user.get('UserID') if acc_type == 'user' else user.get('OwnerID')
            session['owner_id'] = user.get('OwnerID') if acc_type == 'owner' else None
            flash('Login successful', 'success')
            # Redirect users to user dashboard, owners to owner dashboard
            return redirect(url_for('owner_dashboard' if acc_type == 'owner' else 'user_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
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
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        password = request.form.get('password')
        hashed = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO Owners (Name, Email, Phone, Address, Password) VALUES (%s,%s,%s,%s,%s)",
                        (name, email, phone, address, hashed))
            mysql.connection.commit()
            flash('Owner registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Email already registered', 'danger')
        finally:
            cur.close()
    return render_template('owner_register.html')

# ---------- Owner dashboard + Pet CRUD ----------
@app.route('/owner/dashboard')
@login_required(role='owner')
def owner_dashboard():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()

    # Fetch available pets
    cur.execute("SELECT * FROM Pets WHERE OwnerID = %s AND Status = 'available'", (user_id,))
    available_pets = cur.fetchall()

    # Fetch sold pets
    cur.execute("SELECT p.* FROM Pets p JOIN AdoptionHistory ah ON p.PetID = ah.PetID WHERE p.OwnerID = %s", (user_id,))
    sold_pets = cur.fetchall()

    return render_template('owner_dashboard.html', available_pets=available_pets, sold_pets=sold_pets)

@app.route('/owner/pet/add', methods=['GET','POST'])
@login_required(role='owner')
def owner_add_pet():
    if request.method == 'POST':
        owner_id = session.get('owner_id')
        name = request.form.get('name')
        pet_type = request.form.get('type')
        breed = request.form.get('breed')
        
        # Convert age to integer
        try:
            age = int(request.form.get('age', 0))
        except:
            age = 0
        
        gender = request.form.get('gender')
        description = request.form.get('description')
        
        # Convert price to float
        try:
            price = float(request.form.get('price', 0))
        except:
            price = 0.0
        
        # Handle image upload
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # Generate safe filename with timestamp
                    filename = secure_filename(f"{owner_id}_{int(time.time())}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    image_url = f"/static/uploads/pets/{filename}"
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'danger')
                    return render_template('owner_add_pet.html')
            elif file and file.filename:
                flash('Invalid file format. Use PNG, JPG, JPEG, GIF, or WebP', 'danger')
                return render_template('owner_add_pet.html')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO Pets (Name, Type, Breed, Age, Gender, Description, Price, OwnerID, ImageURL, Status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'available')
            """, (name, pet_type, breed, age, gender, description, price, owner_id, image_url))
            mysql.connection.commit()
            cur.close()
            flash('Pet added successfully!', 'success')
            return redirect(url_for('owner_dashboard'))
        except Exception as e:
            flash(f'Error adding pet: {str(e)}', 'danger')
    
    return render_template('owner_add_pet.html')

@app.route('/owner/pet/edit/<int:pet_id>', methods=['GET','POST'])
@login_required(role='owner')
def owner_edit_pet(pet_id):
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Pets WHERE PetID=%s AND OwnerID=%s", (pet_id, owner_id))
    pet = cur.fetchone()
    cur.close()
    
    if not pet:
        flash('Pet not found', 'warning')
        return redirect(url_for('owner_dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        pet_type = request.form.get('type')
        breed = request.form.get('breed')
        
        try:
            age = int(request.form.get('age', 0))
        except:
            age = pet['Age']
        
        gender = request.form.get('gender')
        description = request.form.get('description')
        
        try:
            price = float(request.form.get('price', 0))
        except:
            price = pet['Price']
        
        # Handle new image upload
        image_url = pet['ImageURL']  # Keep existing image by default
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # Delete old image if it exists
                    if pet['ImageURL']:
                        old_file = os.path.join('templates', pet['ImageURL'].lstrip('/'))
                        if os.path.exists(old_file):
                            os.remove(old_file)
                    
                    filename = secure_filename(f"{owner_id}_{int(time.time())}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    image_url = f"/static/uploads/pets/{filename}"
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'danger')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE Pets 
                SET Name=%s, Type=%s, Breed=%s, Age=%s, Gender=%s, Description=%s, Price=%s, ImageURL=%s
                WHERE PetID=%s AND OwnerID=%s
            """, (name, pet_type, breed, age, gender, description, price, image_url, pet_id, owner_id))
            mysql.connection.commit()
            cur.close()
            flash('Pet updated successfully!', 'success')
            return redirect(url_for('owner_dashboard'))
        except Exception as e:
            flash(f'Error updating pet: {str(e)}', 'danger')
    
    return render_template('owner_edit_pet.html', pet=pet)

@app.route('/owner/pet/delete/<int:pet_id>', methods=['POST'])
@login_required(role='owner')
def owner_delete_pet(pet_id):
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT ImageURL FROM Pets WHERE PetID=%s AND OwnerID=%s", (pet_id, owner_id))
    pet = cur.fetchone()
    
    if not pet:
        flash('Pet not found', 'warning')
        return redirect(url_for('owner_dashboard'))
    
    try:
        # Delete image file if exists
        if pet.get('ImageURL'):
            image_file = os.path.join('templates', pet['ImageURL'].lstrip('/'))
            if os.path.exists(image_file):
                os.remove(image_file)
        
        cur.execute("DELETE FROM Pets WHERE PetID=%s AND OwnerID=%s", (pet_id, owner_id))
        mysql.connection.commit()
        flash('Pet deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting pet: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('owner_dashboard'))

# ---------- Adoption requests ----------
@app.route('/adopt/<int:pet_id>', methods=['POST'])
@login_required(role='user')
def adopt(pet_id):
    """User requests adoption for a pet (creates AdoptionRequests row)."""
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    try:
        # Check pet exists and is available
        cur.execute("SELECT PetID, Status, OwnerID FROM Pets WHERE PetID = %s", (pet_id,))
        pet = cur.fetchone()
        if not pet:
            flash('Pet not found', 'danger')
            return redirect(url_for('user_dashboard'))
        if pet['Status'].lower() != 'available':
            flash('Pet is no longer available', 'warning')
            return redirect(url_for('user_dashboard'))

        # Prevent duplicate pending requests by same user for same pet
        cur.execute("""
            SELECT ReqID FROM AdoptionRequests
            WHERE PetID=%s AND UserID=%s AND Status IN ('Pending','pending')
        """, (pet_id, user_id))
        existing = cur.fetchone()
        if existing:
            flash('You already have a pending request for this pet', 'info')
            return redirect(url_for('user_dashboard'))

        # Create request (Message optional)
        message = request.form.get('message', '')
        cur.execute("""
            INSERT INTO AdoptionRequests (UserID, PetID, Message, Status)
            VALUES (%s, %s, %s, %s)
        """, (user_id, pet_id, message, 'Pending'))
        mysql.connection.commit()

        flash('Adoption request sent. Owner will be notified.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        print("Error creating adoption request:", e)
        flash('Could not send request', 'danger')
    finally:
        cur.close()

    return redirect(url_for('user_dashboard'))


@app.route('/my_requests')
@login_required(role='user')
def my_requests():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ar.*, p.Name as PetName, o.Name as OwnerName 
        FROM AdoptionRequests ar 
        JOIN Pets p ON ar.PetID = p.PetID 
        JOIN Owners o ON p.OwnerID = o.OwnerID 
        WHERE ar.UserID=%s
    """, (user_id,))
    requests = cur.fetchall()
    cur.close()
    return render_template('my_requests.html', requests=requests)

@app.route('/owner/requests')
@login_required(role='owner')
def owner_requests():
    owner_id = session.get('owner_id')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ar.*, p.Name as PetName, u.Name as UserName, u.Email, u.Phone
        FROM AdoptionRequests ar
        JOIN Pets p ON ar.PetID = p.PetID
        JOIN Users u ON ar.UserID = u.UserID
        WHERE p.OwnerID=%s
    """, (owner_id,))
    requests = cur.fetchall()
    cur.close()
    return render_template('owner_requests.html', requests=requests)

@app.route('/owner/request/decide/<int:req_id>', methods=['POST'])
@login_required(role='owner')
def owner_decide_request(req_id):
    owner_id = session.get('owner_id')
    decision = request.form.get('decision')
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ar.*, p.OwnerID FROM AdoptionRequests ar
        JOIN Pets p ON ar.PetID = p.PetID
        WHERE ar.ReqID=%s
    """, (req_id,))
    adoption_req = cur.fetchone()
    
    if not adoption_req or adoption_req['OwnerID'] != owner_id:
        flash('Request not found', 'warning')
        return redirect(url_for('owner_requests'))
    
    try:
        cur.execute("UPDATE AdoptionRequests SET Status=%s WHERE ReqID=%s", (decision, req_id))
        mysql.connection.commit()
        flash(f'Request {decision}!', 'success')
    except Exception as e:
        flash('Error updating request', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('owner_requests'))

# ---------- Payments (simple) ----------
@app.route('/payment/<int:req_id>', methods=['GET','POST'])
@login_required(role='user')
def make_payment(req_id):
    if request.method == 'POST':
        user_id = session.get('user_id')
        amount = request.form.get('amount')
        
        try:
            amount = float(amount)
        except:
            flash('Invalid amount', 'danger')
            return redirect(url_for('my_requests'))
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO AdoptionHistory (ReqID, UserID, Amount, PaymentDate)
                VALUES (%s, %s, %s, NOW())
            """, (req_id, user_id, amount))
            
            # Use an existing enum value (e.g. 'Approved') so DB doesn't reject it
            cur.execute("UPDATE AdoptionRequests SET Status=%s WHERE ReqID=%s", ('Approved', req_id))
            cur.execute("UPDATE Pets SET Status='adopted' WHERE PetID=%s", (req_id,))
            mysql.connection.commit()
            flash('Payment successful!', 'success')
            return redirect(url_for('my_history'))
        except Exception as e:
            flash('Payment error', 'danger')
        finally:
            cur.close()
    
    return render_template('payment.html', req_id=req_id)

@app.route('/my_history')
@login_required(role='user')
def my_history():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ah.*, p.Name as PetName, o.Name as OwnerName
        FROM AdoptionHistory ah
        JOIN AdoptionRequests ar ON ah.ReqID = ar.ReqID
        JOIN Pets p ON ar.PetID = p.PetID
        JOIN Owners o ON p.OwnerID = o.OwnerID
        WHERE ah.UserID=%s
        ORDER BY ah.PaymentDate DESC
    """, (user_id,))
    history = cur.fetchall()
    cur.close()
    return render_template('my_history.html', history=history)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.*, o.Name AS OwnerName FROM Pets p 
        JOIN Owners o ON p.OwnerID = o.OwnerID 
        WHERE (p.Name LIKE %s OR p.Type LIKE %s OR p.Breed LIKE %s) AND p.Status='available'
    """, (f'%{query}%', f'%{query}%', f'%{query}%'))
    pets = cur.fetchall()
    cur.close()
    return render_template('index.html', pets=pets, search_query=query)

# add the new user dashboard route
@app.route('/user/dashboard')
@login_required(role='user')
def user_dashboard():
    user_id = session.get('user_id')
    pets = []
    pending = []
    history = []
    pending_payments = 0

    cur = mysql.connection.cursor()
    try:
        # available pets
        cur.execute("""
            SELECT 
                p.PetID, p.Name, p.Type, p.Breed, p.Age, p.Gender, p.Price,
                p.ImageURL, p.Description, p.Status, p.CreatedAt, p.OwnerID,
                o.Name as OwnerName, o.Email as OwnerEmail
            FROM Pets p
            LEFT JOIN Owners o ON p.OwnerID = o.OwnerID
            WHERE p.Status = 'available'
            ORDER BY p.CreatedAt DESC
        """)
        pets = cur.fetchall()

        # pending adoption requests (user side)
        cur.execute("""
            SELECT 
                ar.ReqID, ar.PetID, ar.UserID, ar.Status, ar.CreatedAt,
                p.Name as PetName, p.ImageURL, p.Price, p.Breed, p.Type, p.Age, p.Gender,
                o.Name as OwnerName, o.Email as OwnerEmail
            FROM AdoptionRequests ar
            JOIN Pets p ON ar.PetID = p.PetID
            LEFT JOIN Owners o ON p.OwnerID = o.OwnerID
            WHERE ar.UserID = %s AND ar.Status IN ('Pending','pending')
            ORDER BY ar.CreatedAt DESC
        """, (user_id,))
        pending = cur.fetchall()

        # purchase history (completed adoptions) — read from AdoptionHistory
        cur.execute("""
            SELECT 
                ah.AdoptionID, ah.UserID, ah.PetID, ah.OwnerID, ah.PaymentID, ah.Date as PaymentDate,
                p.Name as PetName, p.ImageURL, p.Price, p.Breed, p.Type, p.Age, p.Gender,
                o.Name as OwnerName, o.Email as OwnerEmail
            FROM AdoptionHistory ah
            JOIN Pets p ON ah.PetID = p.PetID
            LEFT JOIN Owners o ON p.OwnerID = o.OwnerID
            WHERE ah.UserID = %s
            ORDER BY ah.Date DESC
        """, (user_id,))
        history = cur.fetchall()

        # count of approvals from owners (requests approved and awaiting user "payment")
        cur.execute("""
            SELECT COUNT(*) as cnt
            FROM AdoptionRequests
            WHERE UserID = %s AND Status IN ('Approved','approved')
        """, (user_id,))
        row = cur.fetchone()
        pending_payments = int(row['cnt']) if row and 'cnt' in row else 0

    except Exception as e:
        print("Dashboard Error:", e)
        import traceback; traceback.print_exc()
        flash('Error loading dashboard', 'danger')
        pets, pending, history, pending_payments = [], [], [], 0
    finally:
        cur.close()

    return render_template('user_dashboard.html',
                           pets=pets or [],
                           pending=pending or [],
                           history=history or [],
                           pending_payments=pending_payments)

# --- payments pages ---
@app.route('/user/payments')
@login_required(role='user')
def user_payments():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    payments = []
    try:
        cur.execute("""
            SELECT ar.ReqID, ar.PetID, ar.CreatedAt, p.Name AS PetName, p.Price, p.ImageURL, o.Name AS OwnerName, p.OwnerID
            FROM AdoptionRequests ar
            JOIN Pets p ON ar.PetID = p.PetID
            LEFT JOIN Owners o ON p.OwnerID = o.OwnerID
            WHERE ar.UserID = %s AND ar.Status IN ('Approved','approved')
            ORDER BY ar.CreatedAt DESC
        """, (user_id,))
        payments = cur.fetchall()
    except Exception as e:
        print("user_payments error:", e)
        flash('Error loading payments', 'danger')
    finally:
        cur.close()
    return render_template('user_payments.html', payments=payments or [])

@app.route('/user/payment/<int:req_id>', methods=['GET', 'POST'])
@login_required(role='user')
def user_payment(req_id):
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            SELECT ar.ReqID, ar.PetID, ar.Status, ar.CreatedAt,
                   p.Name AS PetName, p.Price, p.ImageURL, p.OwnerID
            FROM AdoptionRequests ar
            JOIN Pets p ON ar.PetID = p.PetID
            WHERE ar.ReqID = %s AND ar.UserID = %s
        """, (req_id, user_id))
        row = cur.fetchone()
        
        if row is None:
            flash('Payment request not found', 'danger')
            return redirect(url_for('user_payments'))
        
        if isinstance(row, dict):
            req = row
        else:
            cols = [d[0] for d in cur.description]
            req = dict(zip(cols, row))

        print("DEBUG: user_payment req:", req)

        owner_id = req.get('OwnerID')
        if not owner_id:
            cur.execute("SELECT OwnerID FROM Pets WHERE PetID = %s", (req['PetID'],))
            r = cur.fetchone()
            if r is None:
                flash('Pet owner not found', 'danger')
                return redirect(url_for('user_payments'))
            if isinstance(r, dict):
                owner_id = r.get('OwnerID')
            else:
                owner_id = r[0]

        if request.method == 'POST':
            now = datetime.utcnow()
            payment_ref = f"MOCK-{uuid.uuid4().hex[:8]}"
            
            print("DEBUG: Payment processed - inserting AdoptionHistory")
            
            # Insert into AdoptionHistory (payment recorded)
            cur.execute("""
                INSERT INTO AdoptionHistory (UserID, PetID, OwnerID, PaymentID, Date)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, req['PetID'], owner_id, None, now))

            # Mark pet as adopted (no longer available on site)
            cur.execute("UPDATE Pets SET Status=%s WHERE PetID=%s", ('adopted', req['PetID']))

            # DELETE the AdoptionRequest so it no longer shows as pending
            cur.execute("DELETE FROM AdoptionRequests WHERE ReqID=%s", (req_id,))

            mysql.connection.commit()
            
            print("DEBUG: Payment successful - redirecting to dashboard")
            flash('Payment successful — adoption completed!', 'success')
            return redirect(url_for('user_dashboard'))

        return render_template('user_payment.html', req=req)

    except Exception as e:
        mysql.connection.rollback()
        import traceback
        traceback.print_exc()
        print("DEBUG: user_payment error:", str(e))
        flash('Could not complete payment', 'danger')
        return redirect(url_for('user_payments'))
    finally:
        cur.close()

if __name__ == '__main__':
    app.run(debug=True)