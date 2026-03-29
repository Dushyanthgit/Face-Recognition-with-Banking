from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mysqldb import MySQL
import face_recognition
import numpy as np
import cv2
import os
import pickle
import random

import google.generativeai as genai


app = Flask(__name__)

genai.configure(api_key="AIzaSyCZuKKo0k6eR_Oy1DrzO8XVOgVBo9_5YMA")

model = genai.GenerativeModel("models/gemini-2.5-flash")

@app.route("/chat", methods=["POST"])
def chat():

    user_message = request.json.get("message")

    with open("allrecordsforbanksystem.txt","r",encoding="utf-8") as f:
        BANK_DATA = f.read()

    prompt = f"""
You are the AI assistant for Face Bank.

Bank Data:
{BANK_DATA}

User Question:
{user_message}
"""

    try:
        response = model.generate_content(prompt)
        reply = response.text
    except Exception as e:
        print("Gemini error:", e)
        reply = "AI error: " + str(e)

    return jsonify({"reply": reply})

app.secret_key = "supersecret"

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Dushyanth789'
app.config['MYSQL_DB'] = 'facebanksystem'

mysql = MySQL(app)

DATASET_PATH = "dataset"

if not os.path.exists(DATASET_PATH):
    os.makedirs(DATASET_PATH)

# ---------------- ACCOUNT NUMBER GENERATOR ----------------
def generate_account_number(phone):
    while True:
        suffix = str(random.randint(100, 999))
        acc_no = phone + suffix   # 10 digit phone + 3 digit suffix = 13
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM users WHERE account_number=%s", (acc_no,))
        existing = cursor.fetchone()
        if not existing:
            return acc_no

#---------------- SERVICES ----------------

@app.route('/services')
def services():
    return render_template("services.html")

#---------------- ABOUT ----------------

@app.route('/about')
def about():
    return render_template("about.html")

#---------------- LOANS ----------------

@app.route('/loans')
def loans():
    return render_template("loans.html")

# ---------------- SCHEMES ----------------

@app.route('/schemes')
def schemes():
    return render_template("schemes.html")

#------------Contact---------------

@app.route('/contact')
def contact():
    return render_template("contact.html")

# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        video = cv2.VideoCapture(0)
        print("Look at camera...")

        while True:
            ret, frame = video.read()
            cv2.imshow("Register - Press S to capture", frame)

            if cv2.waitKey(1) & 0xFF == ord('s'):
                break

        video.release()
        cv2.destroyAllWindows()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)

        if len(encodings) == 0:
            return "Face not detected. Try again."

        encoding = encodings[0]
        encoding_pickle = pickle.dumps(encoding)

        account_number = generate_account_number(phone)

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO users 
            (name,email,phone_number,account_number,balance,face_encoding) 
            VALUES (%s,%s,%s,%s,%s,%s)
        """,(name,email,phone,account_number,100000,encoding_pickle))
        mysql.connection.commit()

        return redirect('/login')

    return render_template("register.html")
# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id,name,face_encoding FROM users WHERE email=%s",(email,))
        user = cursor.fetchone()

        if user is None:
            return "User not found"

        user_id = user[0]
        name = user[1]
        stored_encoding = pickle.loads(user[2])

        video = cv2.VideoCapture(0)

        print("Look at camera and press S")

        while True:
            ret, frame = video.read()
            if not ret:
                continue

            cv2.imshow("Login - Press S to capture", frame)

            if cv2.waitKey(1) & 0xFF == ord('s'):
                break

        video.release()
        cv2.destroyAllWindows()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # detect faces
        face_locations = face_recognition.face_locations(rgb)

        if len(face_locations) == 0:
            return "Face not detected"

        if len(face_locations) > 1:
            return "Multiple faces detected"

        encodings = face_recognition.face_encodings(rgb, face_locations)

        if len(encodings) == 0:
            return "Face encoding failed"

        login_encoding = encodings[0]

        # strict distance check
        distance = face_recognition.face_distance([stored_encoding], login_encoding)

        print("Face distance:", distance[0])

        if distance[0] < 0.40:   # STRICT MATCH
            session['user_id'] = user_id
            session['name'] = name
            return redirect('/dashboard')
        else:
            return "Face not matched"

    return render_template("login.html")


#--------------Admin login------------------
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "admin123":
            session['admin'] = True
            return redirect('/admin_dashboard')

        else:
            return "Invalid Admin Login"

    return render_template("admin_login.html")

#---------Admin dashboard--------------

@app.route("/admin_dashboard")
def admin_dashboard():

    if 'admin' not in session:
        return redirect('/admin_login')

    cursor = mysql.connection.cursor()

    # Total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Total bank balance
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0]

    # Total transactions
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

    # All users
    cursor.execute("""
        SELECT id, name, email, phone_number, account_number, balance, status
        FROM users
    """)
    users = cursor.fetchall()

    # All transactions with sender & receiver names
    cursor.execute("""
        SELECT 
        t.id,
        s.name AS sender_name,
        r.name AS receiver_name,
        t.amount,
        t.type,
        t.balance_after,
        t.created_at
        FROM transactions t
        JOIN users s ON t.sender_id = s.id
        JOIN users r ON t.receiver_id = r.id
        ORDER BY t.created_at DESC
    """)

    transactions = cursor.fetchall()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_balance=total_balance,
        total_transactions=total_transactions,
        users=users,
        transactions=transactions
    )
#-------Freeze Account--------------

@app.route("/admin/freeze/<int:user_id>")
def freeze_account(user_id):

    if 'admin' not in session:
        return redirect('/admin_login')

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET status='frozen' WHERE id=%s", (user_id,))
    mysql.connection.commit()

    return redirect('/admin_dashboard')

#--------------UnFreeze Account-------------


# ---------------- DASHBOARD ----------------

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    # Get user balance and account number
    cursor.execute("SELECT account_number, balance FROM users WHERE id=%s",
                   (session['user_id'],))
    user_data = cursor.fetchone()

    account_number = user_data[0]
    balance = user_data[1]

    # Get transactions where user is sender OR receiver
    cursor.execute("""
        SELECT type, amount, balance_after, created_at
        FROM transactions
        WHERE sender_id = %s OR receiver_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'], session['user_id']))

    transactions = cursor.fetchall()

    return render_template(
        "dashboard.html",
        name=session['name'],
        account_number=account_number,
        balance=balance,
        transactions=transactions
    )

# ---------------- SEARCH ACCOUNT ----------------
@app.route('/search', methods=['POST'])
def search():
    search_value = request.form['search']

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT id,name,account_number 
        FROM users 
        WHERE phone_number=%s OR account_number=%s
    """,(search_value,search_value))

    user = cursor.fetchone()

    if not user:
        return "User not found"

    return render_template("dashboard.html",
                           name=session['name'],
                           search_result=user)

# ---------------- TRANSFER MONEY (ACID SAFE) ----------------
@app.route('/transaction', methods=['POST'])
def transaction():

    if 'user_id' not in session:
        return redirect('/login')

    try:
        receiver_acc = request.form['receiver_account'].strip()
        
        try:
            amount = float(request.form['amount'])
        except:
            return "Invalid amount format"

        if amount <= 0:
            return "Invalid amount"

        cursor = mysql.connection.cursor()

        mysql.connection.begin()  # Atomicity

        # Lock sender
        cursor.execute("""
            SELECT id, balance, status 
            FROM users                  
            WHERE id=%s FOR UPDATE
        """, (session['user_id'],))

        sender = cursor.fetchone()

        if not sender:
            mysql.connection.rollback()
            return "Sender not found"

        sender_id, sender_balance, sender_status = sender

        if sender_status == "frozen":
            mysql.connection.rollback()
            return "Your account is frozen"

        # Lock receiver
        cursor.execute("""
            SELECT id, balance, status 
            FROM users 
            WHERE account_number=%s FOR UPDATE
        """, (receiver_acc,))

        receiver = cursor.fetchone()

        if not receiver:
            mysql.connection.rollback()
            return "Receiver not found"

        receiver_id, receiver_balance, receiver_status = receiver

        if receiver_status == "frozen":
            mysql.connection.rollback()
            return "Receiver account frozen"

        if sender_id == receiver_id:
            mysql.connection.rollback()
            return "Cannot transfer to same account"

        if amount > sender_balance:
            mysql.connection.rollback()
            flash("Insufficient balance", "error")
            return redirect('/dashboard')

        new_sender_balance = sender_balance - amount
        new_receiver_balance = receiver_balance + amount

        # Update balances
        cursor.execute("""
            UPDATE users 
            SET balance=%s 
            WHERE id=%s
        """, (new_sender_balance, sender_id))

        cursor.execute("""
            UPDATE users 
            SET balance=%s 
            WHERE id=%s
        """, (new_receiver_balance, receiver_id))

        # Debit transaction
        cursor.execute("""
            INSERT INTO transactions
            (sender_id, receiver_id, amount, type, balance_after)
            VALUES (%s, %s, %s, %s, %s)
        """, (sender_id, receiver_id, amount, "debit", new_sender_balance))

        # Credit transaction
        cursor.execute("""
            INSERT INTO transactions
            (sender_id, receiver_id, amount, type, balance_after)
            VALUES (%s, %s, %s, %s, %s)
        """, (sender_id, receiver_id, amount, "credit", new_receiver_balance))

        mysql.connection.commit()

        return redirect('/dashboard')

    except Exception as e:
        mysql.connection.rollback()
        print("ERROR:", e)
        return str(e)



# ---------------- LOGOUT ------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)