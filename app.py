import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = 'accounting_secret_key'
DB_NAME = 'double_entry.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS departments (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_no TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        description TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        account_code TEXT NOT NULL,
        dept_code TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        FOREIGN KEY (doc_id) REFERENCES documents(id),
        FOREIGN KEY (account_code) REFERENCES accounts(code),
        FOREIGN KEY (dept_code) REFERENCES departments(code)
    )''')
    
    # Insert some default accounts if empty
    c.execute("SELECT COUNT(*) FROM accounts")
    if c.fetchone()[0] == 0:
        default_accounts = [
            ('1111', 'เงินสด', 'สินทรัพย์'),
            ('1112', 'เงินฝากธนาคาร', 'สินทรัพย์'),
            ('2111', 'เจ้าหนี้การค้า', 'หนี้สิน'),
            ('3111', 'ทุน', 'ส่วนของเจ้าของ'),
            ('4111', 'รายได้ค่าบริการ', 'รายได้'),
            ('5111', 'ค่าใช้จ่ายดำเนินงาน', 'ค่าใช้จ่าย')
        ]
        c.executemany("INSERT INTO accounts (code, name, category) VALUES (?, ?, ?)", default_accounts)
        
        c.execute("INSERT INTO departments (code, name) VALUES (?, ?)", ('01', 'สำนักงานใหญ่'))
    
    conn.commit()
    conn.close()

from flask import session

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        allowed_passwords = ['itech@BalanceX', 'itech@Balance', '1212312121']
        if request.form.get('password') in allowed_passwords:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('รหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# ===================== ACCOUNTS (ผังบัญชี) =====================
@app.route('/accounts', methods=['GET', 'POST'])
def manage_accounts():
    conn = get_db()
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        category = request.form['category']
        try:
            conn.execute("INSERT INTO accounts (code, name, category) VALUES (?, ?, ?)", (code, name, category))
            conn.commit()
            flash('เพิ่มบัญชีสำเร็จ', 'success')
        except sqlite3.IntegrityError:
            flash('รหัสบัญชีซ้ำ', 'danger')
        return redirect(url_for('manage_accounts'))
    
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    conn.close()
    return render_template('accounts.html', accounts=accounts)

@app.route('/delete_account/<code>')
def delete_account(code):
    conn = get_db()
    conn.execute("DELETE FROM accounts WHERE code=?", (code,))
    conn.commit()
    conn.close()
    flash('ลบบัญชีแล้ว', 'success')
    return redirect(url_for('manage_accounts'))

# ===================== DEPARTMENTS (หน่วยงาน) =====================
@app.route('/departments', methods=['GET', 'POST'])
def manage_departments():
    conn = get_db()
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        try:
            conn.execute("INSERT INTO departments (code, name) VALUES (?, ?)", (code, name))
            conn.commit()
            flash('เพิ่มหน่วยงานสำเร็จ', 'success')
        except sqlite3.IntegrityError:
            flash('รหัสหน่วยงานซ้ำ', 'danger')
        return redirect(url_for('manage_departments'))
    
    departments = conn.execute("SELECT * FROM departments ORDER BY code").fetchall()
    conn.close()
    return render_template('departments.html', departments=departments)

# ===================== JOURNAL ENTRY (บันทึกบัญชี) =====================
@app.route('/journal', methods=['GET', 'POST'])
def journal_entry():
    conn = get_db()
    if request.method == 'POST':
        doc_no = request.form['doc_no']
        date = request.form['date']
        description = request.form['description']
        
        account_codes = request.form.getlist('account_code[]')
        dept_codes = request.form.getlist('dept_code[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO documents (doc_no, date, description) VALUES (?, ?, ?)", (doc_no, date, description))
            doc_id = cur.lastrowid
            
            transactions_to_sync = []
            
            for i in range(len(account_codes)):
                ac = account_codes[i]
                dc = dept_codes[i] if dept_codes[i] else None
                dr = float(debits[i]) if debits[i] else 0.0
                cr = float(credits[i]) if credits[i] else 0.0
                
                if ac and (dr > 0 or cr > 0):
                    cur.execute("INSERT INTO transactions (doc_id, account_code, dept_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
                                (doc_id, ac, dc, dr, cr))
                    transactions_to_sync.append({
                        "date": date,
                        "doc_no": doc_no,
                        "description": description,
                        "account_code": ac,
                        "debit": dr,
                        "credit": cr
                    })
            
            conn.commit()
            
            import requests
            import threading
            def sync_to_google(txs):
                url = "https://script.google.com/macros/s/AKfycbxQy-jH6s9rFrkSmTONyVQ31WmobiEGXJxnI3RDDJA3_hOYeqgU0mReYqxacUhn8546oQ/exec"
                for tx in txs:
                    try:
                        requests.post(url, json=tx)
                    except:
                        pass
            threading.Thread(target=sync_to_google, args=(transactions_to_sync,)).start()
            
            flash('บันทึกสมุดรายวันสำเร็จ (พร้อมส่งข้อมูลสำรองขึ้น Google Sheets)', 'success')
            return redirect(url_for('journal_list'))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash('เลขที่เอกสารซ้ำ หรือข้อมูลผิดพลาด', 'danger')
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
            
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    departments = conn.execute("SELECT * FROM departments ORDER BY code").fetchall()
    
    # Auto-generate next doc_no
    last_doc = conn.execute("SELECT doc_no FROM documents ORDER BY id DESC LIMIT 1").fetchone()
    next_doc_no = "JV-0001"
    if last_doc:
        try:
            num = int(last_doc['doc_no'].split('-')[1]) + 1
            next_doc_no = f"JV-{num:04d}"
        except:
            pass
            
    conn.close()
    return render_template('journal_entry.html', accounts=accounts, departments=departments, next_doc_no=next_doc_no)

@app.route('/journal/list')
def journal_list():
    conn = get_db()
    # Fetch all docs with total dr/cr
    docs = conn.execute('''
        SELECT d.*, SUM(t.debit) as total_debit, SUM(t.credit) as total_credit 
        FROM documents d 
        JOIN transactions t ON d.id = t.doc_id 
        GROUP BY d.id 
        ORDER BY d.date DESC, d.id DESC
    ''').fetchall()
    conn.close()
    return render_template('journal_list.html', docs=docs)

# ===================== GENERAL LEDGER (GL) =====================
@app.route('/gl')
def general_ledger():
    conn = get_db()
    account_code = request.args.get('account_code', '')
    
    transactions = []
    if account_code:
        transactions = conn.execute('''
            SELECT d.date, d.doc_no, d.description, t.debit, t.credit, dept.name as dept_name
            FROM transactions t
            JOIN documents d ON t.doc_id = d.id
            LEFT JOIN departments dept ON t.dept_code = dept.code
            WHERE t.account_code = ?
            ORDER BY d.date, d.id
        ''', (account_code,)).fetchall()
        
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    conn.close()
    return render_template('gl.html', accounts=accounts, transactions=transactions, selected_account=account_code)

# ===================== TRIAL BALANCE (TB) =====================
@app.route('/tb')
def trial_balance():
    conn = get_db()
    tb_data = conn.execute('''
        SELECT a.code, a.name, a.category, 
               SUM(t.debit) as sum_dr, SUM(t.credit) as sum_cr
        FROM accounts a
        LEFT JOIN transactions t ON a.code = t.account_code
        GROUP BY a.code
        ORDER BY a.code
    ''').fetchall()
    conn.close()
    return render_template('reports.html', tb_data=tb_data)

# ===================== EXPORT TO EXCEL =====================
import pandas as pd
from io import BytesIO
from flask import send_file

@app.route('/export/gl')
def export_gl():
    conn = get_db()
    account_code = request.args.get('account_code', '')
    if not account_code:
        return "Please select an account first.", 400
        
    transactions = conn.execute('''
        SELECT d.date as "วันที่", d.doc_no as "เลขที่เอกสาร", d.description as "คำอธิบายรายการ", 
               dept.name as "หน่วยงาน", t.debit as "เดบิต", t.credit as "เครดิต"
        FROM transactions t
        JOIN documents d ON t.doc_id = d.id
        LEFT JOIN departments dept ON t.dept_code = dept.code
        WHERE t.account_code = ?
        ORDER BY d.date, d.id
    ''', (account_code,)).fetchall()
    
    account_info = conn.execute("SELECT name FROM accounts WHERE code = ?", (account_code,)).fetchone()
    conn.close()
    
    if not transactions:
        return "ไม่มีข้อมูลสำหรับบัญชีนี้", 404
        
    df = pd.DataFrame([dict(row) for row in transactions])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f"{account_code}")
    output.seek(0)
    
    acc_name = account_info['name'] if account_info else account_code
    filename = f"GL_{account_code}_{acc_name}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

if __name__ == '__main__':
    init_db()
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, port=5000)
