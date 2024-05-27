from flask import Flask, render_template, request, redirect, url_for,flash,session
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
print("Inicializando la aplicación Flask...")
app.secret_key = "hola"

DATABASE = 'credipay.db'

def init_db():
    print("Inicializando la base de datos...")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business TEXT NOT NULL,
            typebusiness TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            dni TEXT NOT NULL,
            rate REAL NOT NULL,
            rate_type TEXT NOT NULL,
            capitalization TEXT NOT NULL,
            credit_line REAL NOT NULL,
            payment_date TEXT NOT NULL,
            late_rate REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente_id INTEGER NOT NULL,
            tipo_operacion TEXT NOT NULL,
            monto REAL NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clients (id)
        )
    ''')
    
    
    conn.commit()
    conn.close()
    print("Base de datos inicializada y tablas creadas.")

def add_user_to_database(username, password, store_name, store_type, first_name, last_name):
    print("Insertando usuario en la base de datos...")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username, password, business, typebusiness, first_name,last_name) VALUES (?, ?, ?, ?, ?,?)',
                   (username, password, store_name, store_type,first_name, last_name))
    conn.commit()
    conn.close()
    print("Usuario insertado correctamente en la base de datos.")
    
def verify_user(username, password):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

def get_clients_for_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, last_name, rate, rate_type, capitalization, credit_line, payment_date FROM clients WHERE user_id = ?', (user_id,))
    clients = cursor.fetchall()
    conn.close()
    return clients

def get_clients_for_user_op(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name FROM clients WHERE user_id = ?', (user_id,))
    clients = cursor.fetchall()
    conn.close()
    return clients


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = verify_user(username, password)
        
        if user:
            print(f"Usuario encontrado: {user}")
            session['user_id'] = user[0]
            session['first_name'] = user[4]
            session['last_name'] = user[5]
            flash('Inicio de sesión exitoso.')
            return redirect(url_for('principal'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        store_name = request.form['store_name']
        store_type = request.form['store_type']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username']
        password = request.form['password']
        
        add_user_to_database(username, password, store_name, store_type, first_name, last_name)
        
        flash('¡Registro exitoso! Ahora puedes iniciar sesión.')
        return redirect(url_for('login')) 
    
    return render_template('register.html')

@app.route('/principal', methods=['GET', 'POST'])
def principal():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    first_name = session.get('first_name')
    last_name = session.get('last_name')
    
    clients = get_clients_for_user(user_id)
    
    print(f"Sesión: first_name={first_name}, last_name={last_name}")  
    return render_template('principal.html', first_name=first_name, last_name=last_name, clients=clients)



@app.route('/newcustomer', methods=['GET', 'POST'])
def newcustomer():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session['user_id']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        dni = request.form['dni']
        rate = request.form['rate']
        rate_type = request.form['rate_type']
        capitalization = request.form['capitalization']
        credit_line = request.form['credit_line']
        payment_date = request.form['payment_date']
        late_rate = request.form['late_rate']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO clients (user_id, first_name, last_name, phone, dni, rate, rate_type, capitalization, credit_line, payment_date, late_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, first_name, last_name, phone, dni, rate, rate_type, capitalization, credit_line, payment_date, late_rate))
        conn.commit()
        conn.close()

        flash('Cliente agregado exitosamente.')
        return redirect(url_for('principal'))

    return render_template('newcustomer.html')

@app.route('/operaciones', methods=['GET', 'POST'])
def operaciones():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        fecha = request.form['fecha']
        cliente_id = request.form['cliente']
        tipo_operacion = request.form['tipo_operacion']
        monto = request.form['monto']
        
        # Aquí puedes procesar la operación y guardarla en la base de datos
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO operaciones (fecha, cliente_id, tipo_operacion, monto)
            VALUES (?, ?, ?, ?)
        ''', (fecha, cliente_id, tipo_operacion, monto))
        conn.commit()
        conn.close()
        
        flash('Operación registrada exitosamente.')
        return redirect(url_for('principal'))

    clients = get_clients_for_user_op(user_id)
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return render_template('operaciones.html', clients=clients, fecha_actual=fecha_actual)


if __name__ == '__main__':
    init_db()  
    
    app.run(debug=True)
