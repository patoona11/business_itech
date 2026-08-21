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

@app.route('/departments/edit/<code>', methods=['POST'])
def edit_department(code):
    conn = get_db()
    new_name = request.form['name']
    conn.execute("UPDATE departments SET name = ? WHERE code = ?", (new_name, code))
    conn.commit()
    conn.close()
    flash('แก้ไขหน่วยงานสำเร็จ', 'success')
    return redirect(url_for('manage_departments'))

@app.route('/departments/delete/<code>')
def delete_department(code):
    conn = get_db()
    conn.execute("DELETE FROM departments WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    flash('ลบหน่วยงานสำเร็จ', 'success')
    return redirect(url_for('manage_departments'))

# ===================== JOURNAL ENTRY (บันทึกบัญชี) =====================
@app.route('/journal', methods=['GET', 'POST'])
def journal_entry():
    conn = get_db()
    if request.method == 'POST':
        doc_no = request.form['doc_no']
        date = request.form['date']
        description = request.form['description']
        reference = request.form.get('reference', '')
        status = request.form.get('status', '1')
        
        account_codes = request.form.getlist('account_code[]')
        dept_codes = request.form.getlist('dept_code[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO documents (doc_no, date, description, reference, status) VALUES (?, ?, ?, ?, ?)", (doc_no, date, description, reference, status))
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
                        "reference": reference,
                        "status": status,
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
            
    accounts = conn.execute("SELECT * FROM accounts WHERE status = 1 ORDER BY code").fetchall()
    departments = conn.execute("SELECT * FROM departments ORDER BY code").fetchall()
    
    # Auto-generate next doc_no
    last_doc = conn.execute("SELECT doc_no FROM documents ORDER BY id DESC LIMIT 1").fetchone()
    next_doc_no = "biz-00001"
    if last_doc:
        try:
            num = int(last_doc['doc_no'].split('-')[1]) + 1
            next_doc_no = f"biz-{num:05d}"
        except:
            pass
            
    conn.close()
    return render_template('journal_entry.html', accounts=accounts, departments=departments, next_doc_no=next_doc_no)

@app.route('/journal/list')
def journal_list():
    conn = get_db()
    query = request.args.get('q', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    sql = '''
        SELECT d.*, SUM(t.debit) as total_debit, SUM(t.credit) as total_credit 
        FROM documents d 
        JOIN transactions t ON d.id = t.doc_id 
        WHERE 1=1
    '''
    params = []
    
    if query:
        sql += " AND (d.doc_no LIKE ? OR d.date LIKE ? OR d.reference LIKE ? OR d.description LIKE ?)"
        search_term = f"%{query}%"
        params.extend([search_term, search_term, search_term, search_term])
        
    if start_date:
        sql += " AND d.date >= ?"
        params.append(start_date)
    
    if end_date:
        sql += " AND d.date <= ?"
        params.append(end_date)
        
    sql += " GROUP BY d.id ORDER BY d.date DESC, d.id DESC"
    
    docs = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('journal_list.html', docs=docs, query=query, start_date=start_date, end_date=end_date)

# ===================== PRINT SPECIFIC JOURNAL =====================
@app.route('/journal/print/<doc_no>')
def print_journal(doc_no):
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE doc_no = ?", (doc_no,)).fetchone()
    if not doc:
        flash('ไม่พบเอกสาร', 'danger')
        conn.close()
        return redirect(url_for('journal_list'))
        
    txs = conn.execute('''
        SELECT t.*, a.name as account_name, d.name as dept_name 
        FROM transactions t
        LEFT JOIN accounts a ON t.account_code = a.code
        LEFT JOIN departments d ON t.dept_code = d.code
        WHERE t.doc_id = ?
    ''', (doc['id'],)).fetchall()
    
    total_dr = sum(tx['debit'] for tx in txs)
    total_cr = sum(tx['credit'] for tx in txs)
    
    conn.close()
    return render_template('jv_print.html', doc=doc, txs=txs, total_dr=total_dr, total_cr=total_cr)

# ===================== EXPORT JOURNAL LIST =====================
@app.route('/export/journal')
def export_journal_list():
    conn = get_db()
    query = request.args.get('q', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    sql = '''
        SELECT d.date as "วันที่", d.doc_no as "เลขที่เอกสาร", d.reference as "อ้างอิง", d.description as "คำอธิบายรายการ",
               SUM(t.debit) as "รวมเดบิต", SUM(t.credit) as "รวมเครดิต"
        FROM documents d 
        JOIN transactions t ON d.id = t.doc_id 
        WHERE 1=1
    '''
    params = []
    
    if query:
        sql += " AND (d.doc_no LIKE ? OR d.date LIKE ? OR d.reference LIKE ? OR d.description LIKE ?)"
        search_term = f"%{query}%"
        params.extend([search_term, search_term, search_term, search_term])
        
    if start_date:
        sql += " AND d.date >= ?"
        params.append(start_date)
        
    if end_date:
        sql += " AND d.date <= ?"
        params.append(end_date)
        
    sql += " GROUP BY d.id ORDER BY d.date DESC, d.id DESC"
    
    docs = conn.execute(sql, params).fetchall()
    conn.close()
    
    if not docs:
        return "ไม่มีข้อมูลสำหรับดาวน์โหลด", 404
        
    df = pd.DataFrame([dict(row) for row in docs])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Journal Register")
    output.seek(0)
    
    filename = f"Journal_Register_{start_date}_to_{end_date}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

# ===================== DELETE JOURNAL ENTRY =====================
@app.route('/journal/delete/<doc_no>', methods=['POST', 'GET'])
def delete_journal(doc_no):
    conn = get_db()
    doc = conn.execute("SELECT id FROM documents WHERE doc_no = ?", (doc_no,)).fetchone()
    if doc:
        conn.execute("DELETE FROM transactions WHERE doc_id = ?", (doc['id'],))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc['id'],))
        conn.commit()
        flash(f'ลบเอกสาร {doc_no} เรียบร้อยแล้ว', 'success')
    else:
        flash('ไม่พบเอกสารที่ต้องการลบ', 'danger')
    conn.close()
    return redirect(url_for('journal_list'))

# ===================== EDIT JOURNAL ENTRY =====================
@app.route('/journal/edit/<doc_no>', methods=['GET', 'POST'])
def edit_journal(doc_no):
    conn = get_db()
    
    # ดึงเอกสารเดิม
    doc = conn.execute("SELECT * FROM documents WHERE doc_no = ?", (doc_no,)).fetchone()
    if not doc:
        flash('ไม่พบเอกสารที่ต้องการแก้ไข', 'danger')
        conn.close()
        return redirect(url_for('journal_list'))
        
    if request.method == 'POST':
        date = request.form['date']
        description = request.form['description']
        reference = request.form.get('reference', '')
        status = request.form.get('status', '1')
        
        account_codes = request.form.getlist('account_code[]')
        dept_codes = request.form.getlist('dept_code[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        
        try:
            cur = conn.cursor()
            # อัปเดตข้อมูลเอกสาร
            cur.execute("UPDATE documents SET date=?, description=?, reference=?, status=? WHERE id=?", 
                        (date, description, reference, status, doc['id']))
            
            # ลบรายการเดิมทั้งหมด
            cur.execute("DELETE FROM transactions WHERE doc_id=?", (doc['id'],))
            
            # บันทึกรายการใหม่
            for i in range(len(account_codes)):
                ac = account_codes[i]
                dc = dept_codes[i] if dept_codes[i] else None
                dr = float(debits[i]) if debits[i] else 0.0
                cr = float(credits[i]) if credits[i] else 0.0
                
                if ac and (dr > 0 or cr > 0):
                    cur.execute("INSERT INTO transactions (doc_id, account_code, dept_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
                                (doc['id'], ac, dc, dr, cr))
            
            conn.commit()
            flash(f'บันทึกการแก้ไขเอกสาร {doc_no} สำเร็จ', 'success')
            return redirect(url_for('journal_list'))
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
            
    # GET Method: ดึงรายการ Transaction เดิมมาแสดง
    txs = conn.execute("SELECT * FROM transactions WHERE doc_id = ?", (doc['id'],)).fetchall()
    
    accounts = conn.execute("SELECT * FROM accounts WHERE status = 1 ORDER BY code").fetchall()
    departments = conn.execute("SELECT * FROM departments ORDER BY code").fetchall()
    conn.close()
    
    return render_template('journal_entry.html', 
                           accounts=accounts, 
                           departments=departments, 
                           edit_doc=doc, 
                           edit_txs=txs)

# ===================== GENERAL LEDGER (GL) =====================
@app.route('/gl')
def general_ledger():
    conn = get_db()
    account_code = request.args.get('account_code', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    transactions = []
    if account_code:
        sql = '''
            SELECT d.date, d.doc_no, d.description, t.account_code, a.name as account_name, t.debit, t.credit, dept.name as dept_name
            FROM transactions t
            JOIN documents d ON t.doc_id = d.id
            LEFT JOIN departments dept ON t.dept_code = dept.code
            LEFT JOIN accounts a ON t.account_code = a.code
            WHERE 1=1
        '''
        params = []
        
        if account_code != 'ALL':
            sql += " AND t.account_code = ?"
            params.append(account_code)
            
        if start_date:
            sql += " AND d.date >= ?"
            params.append(start_date)
            
        if end_date:
            sql += " AND d.date <= ?"
            params.append(end_date)
            
        sql += " ORDER BY t.account_code, d.date, d.id"
        transactions = conn.execute(sql, params).fetchall()
        
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    conn.close()
    return render_template('gl.html', accounts=accounts, transactions=transactions, selected_account=account_code, start_date=start_date, end_date=end_date)

# ===================== TRIAL BALANCE (TB) =====================
@app.route('/tb')
def trial_balance():
    conn = get_db()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND d.date >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND d.date <= ?"
        params.append(end_date)
        
    tb_data = conn.execute(f'''
        SELECT a.code, a.name, a.category, a.status,
               SUM(t.debit) as sum_dr, SUM(t.credit) as sum_cr
        FROM accounts a
        LEFT JOIN transactions t ON a.code = t.account_code
        LEFT JOIN documents d ON t.doc_id = d.id
        WHERE 1=1 {date_filter}
        GROUP BY a.code
        ORDER BY a.code
    ''', params).fetchall()
    conn.close()
    return render_template('reports.html', tb_data=tb_data, start_date=start_date, end_date=end_date)

@app.route('/accounts/toggle_status/<code>', methods=['POST'])
def toggle_account_status(code):
    conn = get_db()
    account = conn.execute("SELECT status FROM accounts WHERE code = ?", (code,)).fetchone()
    if account:
        new_status = 2 if account['status'] == 1 else 1
        conn.execute("UPDATE accounts SET status = ? WHERE code = ?", (new_status, code))
        conn.commit()
        flash('เปลี่ยนสถานะบัญชีสำเร็จ', 'success')
    conn.close()
    return redirect(url_for('trial_balance'))

# ===================== EXPORT TO EXCEL =====================
import pandas as pd
from io import BytesIO
from flask import send_file

@app.route('/export/gl')
def export_gl():
    conn = get_db()
    account_code = request.args.get('account_code', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if not account_code:
        return "Please select an account first.", 400
        
    sql = '''
        SELECT d.date as "วันที่", d.doc_no as "เลขที่เอกสาร", d.description as "คำอธิบายรายการ", 
               dept.name as "หน่วยงาน", t.debit as "เดบิต", t.credit as "เครดิต"
        FROM transactions t
        JOIN documents d ON t.doc_id = d.id
        LEFT JOIN departments dept ON t.dept_code = dept.code
        WHERE 1=1
    '''
    params = []
    
    if account_code != 'ALL':
        sql += " AND t.account_code = ?"
        params.append(account_code)
        
    if start_date:
        sql += " AND d.date >= ?"
        params.append(start_date)
        
    if end_date:
        sql += " AND d.date <= ?"
        params.append(end_date)
        
    sql += " ORDER BY t.account_code, d.date, d.id"
    transactions = conn.execute(sql, params).fetchall()
    
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

@app.route('/export/tb')
def export_tb():
    conn = get_db()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND d.date >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND d.date <= ?"
        params.append(end_date)
        
    tb_data = conn.execute(f'''
        SELECT a.code as "รหัสบัญชี", a.name as "ชื่อบัญชี", a.category as "หมวด", 
               SUM(t.debit) as "เดบิต", SUM(t.credit) as "เครดิต"
        FROM accounts a
        LEFT JOIN transactions t ON a.code = t.account_code
        LEFT JOIN documents d ON t.doc_id = d.id
        WHERE 1=1 {date_filter}
        GROUP BY a.code
        ORDER BY a.code
    ''', params).fetchall()
    conn.close()
    
    if not tb_data:
        return "ไม่มีข้อมูล", 404
        
    df = pd.DataFrame([dict(row) for row in tb_data])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Trial Balance")
    output.seek(0)
    
    filename = f"Trial_Balance_{start_date}_to_{end_date}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

if __name__ == '__main__':
    init_db()
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, port=5000)
