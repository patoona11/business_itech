from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DB_NAME = 'accounting.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM transactions ORDER BY date DESC, id DESC')
    transactions = c.fetchall()
    
    total_income = sum(t['amount'] for t in transactions if t['type'] == 'รายรับ')
    total_expense = sum(t['amount'] for t in transactions if t['type'] == 'รายจ่าย')
    net_balance = total_income - total_expense
    
    conn.close()
    return render_template('index.html', transactions=transactions, 
                           total_income=total_income, total_expense=total_expense, 
                           net_balance=net_balance)

@app.route('/add', methods=['POST'])
def add_transaction():
    date = request.form['date']
    description = request.form['description']
    tx_type = request.form['type']
    amount = request.form['amount']
    
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO transactions (date, description, type, amount) VALUES (?, ?, ?, ?)',
              (date, description, tx_type, amount))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_transaction(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    # Create templates directory if not exists
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, port=5000)
