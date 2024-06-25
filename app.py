from flask import Flask, render_template, request, redirect, url_for,flash,session,jsonify
import sqlite3
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
app = Flask(__name__)
print("Inicializando la aplicación Flask...")
app.secret_key = "hola"

DATABASE = 'credi_pay.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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



def get_clients_for_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name, phone,dni, rate, rate_type, capitalization, credit_line, payment_date,late_rate FROM clients WHERE user_id = ?', (user_id,))
    clients = cursor.fetchall()

    clients_with_operations = []
    for client in clients:
        client_id = client[0]
        payment_date = datetime.strptime(client[9], '%Y-%m-%d')
        
        
        try:
            if datetime.now() > payment_date:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=payment_date.day)
            else:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=payment_date.day - 1)
        except ValueError:
            
            last_day_of_prev_month = (payment_date.replace(day=1) - timedelta(days=1)).day
            if datetime.now() > payment_date:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=min(payment_date.day, last_day_of_prev_month))
            else:
                start_date = payment_date.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=min(payment_date.day - 1, last_day_of_prev_month))

        cursor.execute('''
            SELECT SUM(monto), SUM(montopago) FROM operaciones 
            WHERE cliente_id = ?  AND fecha BETWEEN ? AND ?
        ''', (client_id, start_date.strftime('%Y-%m-%d'), payment_date.strftime('%Y-%m-%d')))
        
        result = cursor.fetchone()
        monto_consumido = result[0] or 0
        monto_a_pagar = result[1] or 0
        saldo = client[8] - monto_consumido
        
        clients_with_operations.append(client + (monto_consumido, saldo, monto_a_pagar))

    conn.close()
    return clients_with_operations

def add_operacion(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa,capitalization):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    if tipo_operacion == 'pago':
        monto = -float(monto)
    else:
        monto = float(monto)

    cursor.execute('SELECT payment_date FROM clients WHERE id = ?', (cliente_id,))
    payment_date_str = cursor.fetchone()[0]
    payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d')

    fecha_operacion = datetime.strptime(fecha, '%Y-%m-%d')
    monto_pago = calcular_monto_pago(float(monto), float(tasa_operacion), tipo_tasa,  capitalization,fecha_operacion, payment_date)

    cursor.execute('''
        INSERT INTO operaciones (fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipotasa_operacion, montopago, periodo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa, monto_pago, payment_date.strftime('%m%y')))
    
    conn.commit()
    conn.close()
    
def add_operacion_cuotas(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa, capitalization, num_cuotas,plazo):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    num_cuotas = int(num_cuotas)
    plazo=int(plazo)
    cursor.execute('SELECT payment_date FROM clients WHERE id = ?', (cliente_id,))
    payment_date_str = cursor.fetchone()[0]
    payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d')
    
    if tipo_tasa == 'TEA':
        tfc= ((1 + float(tasa_operacion)/100)(30 / 360))-1
    elif tipo_tasa == 'TET':
        tfc= ((1 + float(tasa_operacion)/100)(30 / 90))-1
    elif tipo_tasa == 'TEM':
        tfc= tasa_operacion
    elif tipo_tasa == 'TEC':
        tfc= ((1 + float(tasa_operacion)/100)(30 / 120))-1
    elif tipo_tasa == 'TEB':
        tfc= ((1 + float(tasa_operacion)/100)(30 / 60))-1
    elif tipo_tasa == 'TES':
        tfc= ((1 + float(tasa_operacion)/100)(30 / 180))-1
    elif tipo_tasa == 'TNS':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/6)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/12)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/180)(30))-1
    elif tipo_tasa == 'TNM':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/1)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/2)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/30)(30))-1
    elif tipo_tasa == 'TNB':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/2)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/4)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/60)(30))-1
    elif tipo_tasa == 'TNC':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/4)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/8)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/120)(30))-1
    elif tipo_tasa == 'TNT':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/3)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/6)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/90)(30))-1
    elif tipo_tasa == 'TNA':
        if capitalization=='mensual':
            tfc= ((1 + (float(tasa_operacion)/100)/12)(1 ))-1
        if capitalization=='quincenal':
            tfc= ((1 + (float(tasa_operacion)/100)/24)(2))-1
        if capitalization=='diaria':
            tfc= ((1 + (float(tasa_operacion)/100)/360)(30))-1
    
    new_payment_date = payment_date + relativedelta(months=num_cuotas -1 ) 
    fecha_operacion = datetime.strptime(fecha, '%Y-%m-%d')
    montonuevo=calcular_monto_pago(float(monto),float(tasa_operacion),tipo_tasa,capitalization,fecha_operacion,payment_date)
    
    tfc=float(tfc)
    print(montonuevo)
    print(tfc)
    fecha_operacion= fecha_operacion + relativedelta(months=plazo)
    num=tfc*((1+tfc)**num_cuotas)
    print(num)
    div=((1+tfc)**num_cuotas)-1
    print(div)
    q=num/div
    print(q)
    monto_cuota = float(montonuevo)*(q)
    monto_divido=float(monto)/num_cuotas


    for cuota in range(0, int(num_cuotas) ):
        cuota_payment_date = fecha_operacion + relativedelta(months=cuota)
        cuota_periodo = cuota_payment_date.strftime('%m%y')

        cursor.execute('''
            INSERT INTO operaciones (fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipotasa_operacion, montopago, periodo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cuota_payment_date.strftime('%Y-%m-%d'), cliente_id, tipo_operacion, monto_divido, tasa_operacion, tipo_tasa, monto_cuota, cuota_periodo))

    conn.commit()
    conn.close()

def calcular_monto_pago(monto, tasa, tasa_tipo,capitalization, fecha_operacion, fecha_pago):
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
    elif tasa_tipo == 'TNS':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(180/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(180/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(180)) / 100) ** (dias)
    elif tasa_tipo == 'TNM':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(30/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(30/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(30)) / 100) ** (dias)
    elif tasa_tipo == 'TNB':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(60/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(60/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(60)) / 100) ** (dias)
    elif tasa_tipo == 'TNC':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(120/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(120/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(120)) / 100) ** (dias)
    elif tasa_tipo == 'TNT':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(90/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(90/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(90)) / 100) ** (dias)
    elif tasa_tipo == 'TNA':
        if capitalization=='mensual':
            return monto * (1 + (tasa/(360/30)) / 100) ** (dias / 30)
        if capitalization=='quincenal':
            return monto * (1 + (tasa/(360/15)) / 100) ** (dias / 15)
        if capitalization=='diaria':
            return monto * (1 + (tasa/(360)) / 100) ** (dias)
    else:
        return monto


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

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    clients = get_clients_for_user(user_id)
    
    
    
    return render_template('clientes.html', clients=clients)

@app.route('/update_cliente', methods=['POST'])
def update_cliente():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.json
    client_id = data['id']
    first_name = data['first_name']
    last_name = data['last_name']
    phone = data['phone']
    dni = data['dni']
    rate = data['rate']
    rate_type = data['rate_type']
    capitalization = data['capitalization']
    credit_line = data['credit_line']
    payment_date = data['payment_date']
    late_rate = data['late_rate']

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE clients
        SET first_name = ?, last_name = ?, phone = ?, dni = ?, rate = ?, rate_type = ?, capitalization = ?, credit_line = ?, payment_date = ?, late_rate = ?
        WHERE id = ?
    """, (first_name, last_name, phone, dni, rate, rate_type, capitalization, credit_line, payment_date, late_rate, client_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

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

@app.route('/get_saldo/<int:cliente_id>', methods=['GET'])
def get_saldo(cliente_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.credit_line - COALESCE(SUM(o.monto), 0) 
        FROM clients c
        LEFT JOIN operaciones o ON c.id = o.cliente_id
        WHERE c.id = ?
    ''', (cliente_id,))
    
    saldo = cursor.fetchone()[0]
    conn.close()
    
    return jsonify(saldo=saldo)



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
        capitalization = request.form['capitalization']

        if  request.form['num_cuotas']:
            num_cuotas = request.form['num_cuotas']
            plazo = request.form['plazo']
            add_operacion_cuotas(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa, capitalization, num_cuotas,plazo)
            flash('Operación registrada a cuotas exitosamente.')
        else:
            add_operacion(fecha, cliente_id, tipo_operacion, monto, tasa_operacion, tipo_tasa, capitalization)
            flash('Operación registrada exitosamente.')
        
        update_cliente(cliente_id, tasa_operacion, tipo_tasa, capitalization)
        return redirect(url_for('principal'))

    clients = get_clients_for_user(user_id)
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return render_template('operaciones.html', clients=clients, fecha_actual=fecha_actual)


def update_cliente(cliente_id, new_rate, new_rate_type, new_capitalization):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE clients
        SET rate = ?, rate_type = ?, capitalization = ?
        WHERE id = ?
    ''', (new_rate, new_rate_type, new_capitalization, cliente_id))
    conn.commit()
    conn.close()

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
    fecha_de_pago = None
    monto_final_a_pagar = 0
    
    if request.method == 'POST':
        selected_client = int(request.form['cliente'])
        selected_periodo = request.form['periodo']
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT o.id, o.fecha, c.credit_line, o.tasa_operacion, o.tipotasa_operacion, o.monto, o.montopago, c.payment_date 
            FROM operaciones o
            JOIN clients c ON o.cliente_id = c.id
            WHERE o.cliente_id = ? AND o.periodo = ?
        ''', (selected_client, selected_periodo))
        
        operaciones = cursor.fetchall()
        conn.close()
        
        if operaciones:
            fecha_de_pago = operaciones[0][7] 
            monto_final_a_pagar = sum(op[6] for op in operaciones)

    return render_template('reportes.html', clients=clients, operaciones=operaciones, 
                           selected_client=selected_client, selected_periodo=selected_periodo, 
                           fecha_de_pago=fecha_de_pago, monto_final_a_pagar=monto_final_a_pagar,enumerate=enumerate, datetime=datetime)



if __name__ == '__main__':
    init_db()  
    
    app.run(host='0.0.0.0', port=8080)
