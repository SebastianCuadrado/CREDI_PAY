from flask import Flask, render_template, request, redirect, url_for,flash,session,jsonify
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
print("Inicializando la aplicación Flask...")
app.secret_key = "hola"

DATABASE = 'credi_pay.db'

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
            periodo TEXT,
            tasa_operacion REAL,
            tipotasa_operacion TEXT,
            montopago REAL,
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

def calcular_monto_pago(monto, tasa, tasa_tipo, fecha_operacion, fecha_pago):
    dias = (fecha_pago - fecha_operacion).days
    if tasa_tipo == 'TEA':
        return monto * (1 + tasa / 100) ** (dias / 360)
    elif tasa_tipo == 'TET':
        return monto * (1 + tasa / 100) ** (dias / 90)
    elif tasa_tipo == 'TEC':
        return monto * (1 + tasa / 100) ** (dias / 120)
    elif tasa_tipo == 'TEB':
        return monto * (1 + tasa / 100) ** (dias / 60)
    elif tasa_tipo == 'TEM':
        return monto * (1 + tasa / 100) ** (dias / 30)
    elif tasa_tipo == 'TES':
        return monto * (1 + tasa / 100) ** (dias / 180)
    else:
        return monto

def get_clients_for_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name, rate, rate_type, capitalization, credit_line, payment_date FROM clients WHERE user_id = ?', (user_id,))
    clients = cursor.fetchall()

    clients_with_operations = []
    for client in clients:
        client_id = client[0]
        payment_date = datetime.strptime(client[7], '%Y-%m-%d')
        
        # Ajustar la fecha de inicio correctamente para evitar errores de fecha
        try:
            if datetime.now() > payment_date:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=payment_date.day)
            else:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=payment_date.day - 1)
        except ValueError:
            # Manejo de errores en caso de que el día sea inválido para el mes anterior
            last_day_of_prev_month = (payment_date.replace(day=1) - timedelta(days=1)).day
            if datetime.now() > payment_date:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=min(payment_date.day, last_day_of_prev_month))
            else:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=min(payment_date.day - 1, last_day_of_prev_month))

        cursor.execute('''
            SELECT SUM(monto) FROM operaciones 
            WHERE cliente_id = ? AND tipo_operacion = 'consumo' AND fecha BETWEEN ? AND ?
        ''', (client_id, start_date.strftime('%Y-%m-%d'), payment_date.strftime('%Y-%m-%d')))
        
        monto_consumido = cursor.fetchone()[0] or 0
        saldo = client[6] - monto_consumido
        
        clients_with_operations.append(client + (monto_consumido, saldo))

    conn.close()
    return clients_with_operations

def add_operacion(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('SELECT payment_date FROM clients WHERE id = ?', (cliente_id,))
    payment_date_str = cursor.fetchone()[0]
    payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d')

    fecha_operacion = datetime.strptime(fecha, '%Y-%m-%d')
    monto_pago = calcular_monto_pago(float(monto), float(tasa_operacion), tipo_tasa, fecha_operacion, payment_date)

    cursor.execute('''
        INSERT INTO operaciones (fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipotasa_operacion, montopago, periodo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa, monto_pago, payment_date.strftime('%m%y')))
    
    conn.commit()
    conn.close()




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
        payment_day = int(request.form['payment_day'])
        late_rate = request.form['late_rate']
        
        today = datetime.today()
        today = datetime.today()
        if today.day > payment_day:
            payment_date = (today.replace(day=1) + timedelta(days=32)).replace(day=payment_day)
        else:
            payment_date = today.replace(day=payment_day)
          
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clients (user_id, first_name, last_name, phone, dni, rate, rate_type, capitalization, credit_line, payment_date, late_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, first_name, last_name, phone, dni, rate, rate_type, capitalization, credit_line, payment_date.strftime('%Y-%m-%d'), late_rate))
        conn.commit()
        conn.close()
        
        flash('Cliente creado exitosamente.')
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
        tasa_operacion = request.form['rate']
        tipo_tasa = request.form['rate_type']
        
        add_operacion(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa)
        
        flash('Operación registrada exitosamente.')
        return redirect(url_for('principal'))

    clients = get_clients_for_user(user_id)
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return render_template('operaciones.html', clients=clients, fecha_actual=fecha_actual)

@app.route('/get_periodos/<int:cliente_id>', methods=['GET'])
def get_periodos(cliente_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT periodo FROM operaciones WHERE cliente_id = ?', (cliente_id,))
    periodos = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(periodos)

@app.route('/reportes', methods=['GET', 'POST'])
def reportes():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    clients = get_clients_for_user(user_id)
    
    operaciones = None
    selected_client = None
    selected_periodo = None
    
    if request.method == 'POST':
        selected_client = int(request.form['cliente'])
        selected_periodo = request.form['periodo']
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT o.id, o.fecha, c.credit_line, o.tasa_operacion, o.tipotasa_operacion, o.monto,o.montopago, c.payment_date 
            FROM operaciones o
            JOIN clients c ON o.cliente_id = c.id
            WHERE o.cliente_id = ? AND o.periodo = ?
        ''', (selected_client, selected_periodo))
        
        operaciones = cursor.fetchall()
        conn.close()
    
    return render_template('reportes.html', clients=clients, operaciones=operaciones, 
                           selected_client=selected_client, selected_periodo=selected_periodo, 
                           enumerate=enumerate, datetime=datetime)


if __name__ == '__main__':
    init_db()  
    
    app.run(debug=True)
