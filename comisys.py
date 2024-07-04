import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Conectar ao banco de dados


def get_db_connection():
    conn = sqlite3.connect('sales_tracking.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar o banco de dados


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Criar tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL  -- 'seller' or 'master'
    );
    ''')

    # Criar tabela de metas individuais
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS IndividualGoals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        goal REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES Users(id)
    );
    ''')

    # Criar tabela de metas gerais
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS GeneralGoals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal REAL NOT NULL
    );
    ''')

    # Criar tabela de vendas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        amount REAL NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES Users(id)
    );
    ''')

    conn.commit()
    conn.close()


# Chamar a função de inicialização do banco de dados
init_db()

# Rota inicial


@app.route('/')
def index():
    return render_template('index.html')

# Rota para registro


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Users (username, password, role) VALUES (?, ?, ?)',
                       (username, hashed_password, role))
        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!')
        return redirect(url_for('login'))

    return render_template('register.html')

# Rota para login


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash('Login inválido, verifique suas credenciais.')

    return render_template('login.html')

# Rota para dashboard


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_role = session['role']

    conn = get_db_connection()
    cursor = conn.cursor()

    if user_role == 'seller':
        cursor.execute('''
            SELECT SUM(amount) AS total_sales 
            FROM Sales 
            WHERE user_id = ? 
            AND strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''', (user_id,))
        total_sales_row = cursor.fetchone()
        total_sales = total_sales_row['total_sales'] if total_sales_row['total_sales'] and total_sales_row['total_sales'] else 0

        cursor.execute('SELECT goal FROM IndividualGoals WHERE user_id = ?', (user_id,))
        individual_goal_row = cursor.fetchone()
        individual_goal = individual_goal_row['goal'] if individual_goal_row else 0

        cursor.execute('''
            SELECT SUM(amount) AS total_company_sales 
            FROM Sales 
            WHERE strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''')
        total_company_sales_row = cursor.fetchone()
        total_company_sales = total_company_sales_row['total_company_sales'] if total_company_sales_row and total_company_sales_row['total_company_sales'] else 0

        cursor.execute('SELECT goal FROM GeneralGoals ORDER BY id DESC LIMIT 1')
        general_goal_row = cursor.fetchone()
        general_goal = general_goal_row['goal'] if general_goal_row else 0

        # Obter vendas do vendedor no mês atual
        cursor.execute('''
            SELECT date, amount 
            FROM Sales 
            WHERE user_id = ? 
            AND strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''', (user_id,))
        vendas = cursor.fetchall()

        conn.close()

        individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
        company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0

        return render_template('seller_dashboard.html', total_sales=total_sales,
                               total_company_sales=total_company_sales, individual_percentage=individual_percentage,
                               company_percentage=company_percentage,
                               user_id=user_id,
                               general_goal=general_goal,
                               vendas=vendas)
    elif user_role == 'master':
        cursor.execute('SELECT id, username FROM Users WHERE role = "seller"')
        sellers = cursor.fetchall()

        cursor.execute('SELECT goal FROM GeneralGoals ORDER BY id DESC LIMIT 1')
        general_goal_row = cursor.fetchone()
        general_goal = general_goal_row['goal'] if general_goal_row else 0

        return render_template('master_dashboard.html', sellers=sellers, general_goal=general_goal)

# Rota dinâmica para o dashboard de um vendedor específico


@app.route('/dashboard/<int:seller_id>')
def seller_dashboard(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(amount) AS total_sales 
        FROM Sales 
        WHERE user_id = ? 
        AND strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
    ''', (seller_id,))
    total_sales_row = cursor.fetchone()
    total_sales = total_sales_row['total_sales'] if total_sales_row and total_sales_row['total_sales'] else 0

    cursor.execute('SELECT goal FROM IndividualGoals WHERE user_id = ?', (seller_id,))
    individual_goal_row = cursor.fetchone()
    individual_goal = individual_goal_row['goal'] if individual_goal_row else 0

    cursor.execute('''
        SELECT SUM(amount) AS total_company_sales 
        FROM Sales 
        WHERE strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
    ''')
    total_company_sales_row = cursor.fetchone()
    total_company_sales = total_company_sales_row['total_company_sales'] if total_company_sales_row and total_company_sales_row['total_company_sales'] else 0

    cursor.execute('SELECT goal FROM GeneralGoals ORDER BY id DESC LIMIT 1')
    general_goal_row = cursor.fetchone()
    general_goal = general_goal_row['goal'] if general_goal_row else 0

    # Obter vendas do vendedor no mês atual
    cursor.execute('''
        SELECT date, amount 
        FROM Sales 
        WHERE user_id = ? 
        AND strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
    ''', (seller_id,))
    vendas = cursor.fetchall()
    
    conn.close()

    individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
    company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0

    return render_template(
        'seller_dashboard.html',
        total_sales=total_sales,
        total_company_sales=total_company_sales,
        individual_percentage=individual_percentage,
        company_percentage=company_percentage,
        user_id=seller_id,
        general_goal=general_goal,
        vendas=vendas)


# Rota para logout


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Rota para upload de planilha


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)

        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            process_file(file_path)
            flash('Arquivo processado com sucesso!')
            # return redirect(url_for('dashboard'))

    return render_template('upload.html')


def process_file(file_path):
    try:
        df = pd.read_excel(file_path)

        # Verificar se as colunas necessárias estão presentes
        required_columns = {'data', 'valor', 'id_vendedor'}
        if not required_columns.issubset(df.columns):
            flash('Faltam colunas necessárias na planilha.')
            return

        # Verificar se as colunas estão no formato correto
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
        df['id_vendedor'] = pd.to_numeric(df['id_vendedor'], errors='coerce')

        if df['data'].isnull().any() or df['valor'].isnull().any() or df['id_vendedor'].isnull().any():
            flash('A planilha contém dados inválidos.')
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        for index, row in df.iterrows():
            cursor.execute('''
                INSERT INTO Sales (date, amount, user_id)
                VALUES (?, ?, ?)
            ''', (row['data'], row['valor'], row['id_vendedor']))

        conn.commit()
        conn.close()

        flash('Arquivo processado com sucesso!')
    except Exception as e:
        flash(f'Ocorreu um erro ao processar o arquivo: {e}')


# Rota para definir metas


@app.route('/set_goals', methods=['GET', 'POST'])
def set_goals():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        individual_goal = request.form['individual_goal']
        general_goal = request.form['general_goal']
        user_id = request.form['user_id']

        # Atualizar ou inserir meta individual
        cursor.execute('SELECT * FROM IndividualGoals WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE IndividualGoals SET goal = ? WHERE user_id = ?', (individual_goal, user_id))
        else:
            cursor.execute('INSERT INTO IndividualGoals (user_id, goal) VALUES (?, ?)', (user_id, individual_goal))

        # Atualizar meta geral (apenas uma entrada)
        cursor.execute('SELECT * FROM GeneralGoals')
        if cursor.fetchone():
            cursor.execute('UPDATE GeneralGoals SET goal = ? WHERE id = 1', (general_goal,))
        else:
            cursor.execute('INSERT INTO GeneralGoals (goal) VALUES (?)', (general_goal,))

        conn.commit()
        conn.close()

        flash('Metas atualizadas com sucesso!')
        return redirect(url_for('dashboard'))

    # Buscar vendedores para selecionar nas metas individuais
    cursor.execute('SELECT id, username FROM Users WHERE role = "seller"')
    sellers = cursor.fetchall()

    conn.close()
    return render_template('set_goals.html', sellers=sellers)


if __name__ == '__main__':
    app.run(debug=True)
