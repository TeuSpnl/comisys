import datetime
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import unicodedata

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
        name TEXT NOT NULL,  -- Nome completo do usuário
        role TEXT NOT NULL  -- 'seller' ou 'master'
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
        order_number TEXT NOT NULL,
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
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Users (username, password, name, role) VALUES (?, ?, ?, ?)',
                       (username, hashed_password, name, role))
        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!', 'success')

    return render_template('register.html')


@app.route('/delete_seller/<int:seller_id>', methods=['POST'])
def delete_seller(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Users WHERE id = ? AND role = "seller"', (seller_id,))
    conn.commit()
    conn.close()

    flash('Vendedor deletado com sucesso!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update_password/<int:seller_id>', methods=['GET', 'POST'])
def update_password(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE Users SET password = ? WHERE id = ? AND role = "seller"', (hashed_password, seller_id))
        conn.commit()
        conn.close()

        flash('Senha do vendedor atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM Users WHERE id = ? AND role = "seller"', (seller_id,))
    seller = cursor.fetchone()
    conn.close()

    if not seller:
        flash('Vendedor não encontrado!', 'error')
        return redirect(url_for('dashboard'))

    return render_template('update_password.html', seller=seller)


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
            flash('Login inválido, verifique suas credenciais.', 'error')

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
        cursor.execute('SELECT name FROM Users WHERE id = ?', (user_id,))
        username = cursor.fetchone()['name']

        cursor.execute('''
            SELECT SUM(amount) AS total_sales
            FROM Sales
            WHERE user_id = ?
            AND strftime('%m', date) = strftime('%m', 'now')
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''', (user_id,))
        total_sales_row = cursor.fetchone()
        total_sales = total_sales_row['total_sales'] if total_sales_row and total_sales_row['total_sales'] else 0

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

        # Obter vendas do vendedor no mês atual, ordenadas por data
        cursor.execute('''
            SELECT id, date, amount, order_number
            FROM Sales
            WHERE user_id = ?
            AND strftime('%m', date) = strftime('%m', 'now')
            AND strftime('%Y', date) = strftime('%Y', 'now')
            ORDER BY date DESC
        ''', (user_id,))
        vendas = cursor.fetchall()

        conn.close()

        individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
        company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0

        # Calcular a comissão com base nas metas individuais atingidas
        commission_rate = 0.01
        bonus_rate = 0
        if total_sales >= 225000:
            bonus_rate += 0.006
        elif total_sales >= 170000:
            bonus_rate += 0.004
        elif total_sales >= 130000:
            bonus_rate += 0.003

        commission = total_sales * commission_rate
        bonus = total_sales * bonus_rate

        return render_template('seller_dashboard.html',
                               user_role=user_role,
                               total_sales=total_sales,
                               total_company_sales=total_company_sales,
                               individual_percentage=individual_percentage,
                               company_percentage=company_percentage,
                               user_id=user_id,
                               username=username,
                               general_goal=general_goal,
                               vendas=vendas,
                               bonus=bonus,
                               commission=commission,
                               individual_goal=individual_goal)
    elif user_role == 'master':
        cursor.execute('SELECT id, username, name FROM Users WHERE role = "seller"')
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

    # Obter vendas do vendedor no mês atual, ordenadas por data
    cursor.execute('''
        SELECT id, date, amount, order_number
        FROM Sales
        WHERE user_id = ?
        AND strftime('%m', date) = strftime('%m', 'now')
        AND strftime('%Y', date) = strftime('%Y', 'now')
        ORDER BY order_number DESC
    ''', (seller_id,))
    vendas = cursor.fetchall()

    # Obter vendedores do banco de dados
    cursor.execute('''SELECT name FROM Users WHERE id = ?''', (seller_id,))
    name = cursor.fetchall()

    conn.close()

    individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
    company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0

    # Calcular a comissão com base nas metas individuais atingidas
    commission_rate = 0.01
    bonus_rate = 0
    if total_sales >= 225000:
        bonus_rate += 0.006
    elif total_sales >= 170000:
        bonus_rate += 0.004
    elif total_sales >= 130000:
        bonus_rate += 0.003

    commission = total_sales * commission_rate
    bonus = total_sales * bonus_rate

    return render_template(
        'seller_dashboard.html',
        user_role=session['role'],
        total_sales=total_sales,
        total_company_sales=total_company_sales,
        individual_percentage=individual_percentage,
        company_percentage=company_percentage,
        user_id=seller_id,
        general_goal=general_goal,
        vendas=vendas,
        commission=commission,
        bonus=bonus,
        username=name[0]['name'],
        individual_goal=individual_goal)


@app.route('/delete_sale/<int:sale_id>', methods=['POST'])
def delete_sale(sale_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Sales WHERE id = ?', (sale_id,))
    conn.commit()
    conn.close()

    flash('Venda deletada com sucesso!', 'success')
    return redirect(request.referrer)


@app.route('/delete_all_sales/<int:seller_id>', methods=['POST'])
def delete_all_sales(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Sales WHERE user_id = ?', (seller_id,))
    conn.commit()
    conn.close()

    flash('Todas as vendas foram deletadas com sucesso!', 'success')
    return redirect(request.referrer)

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
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            process_file(file_path)
            # return redirect(url_for('dashboard'))

    return render_template('upload.html')


def process_file(file_path):
    try:
        df = pd.read_excel(file_path, header=None)

        # Identificar a linha inicial da tabela
        start_row = None
        for i, row in df.iterrows():
            if 'data' in row.astype(str).str.lower().tolist():
                start_row = i
                break

        if start_row is None:
            flash('Não foi possível identificar a linha inicial da tabela.', 'error')
            return

        df = pd.read_excel(file_path, skiprows=start_row)

        # Renomear as colunas para facilitar o acesso
        df.columns = [str(col).strip().lower() for col in df.columns]

        # Identificar o fim da tabela com base na consistência dos dados
        df = df.dropna(how='all')  # Remove linhas completamente vazias
        df = df.reset_index(drop=True)

        # Filtrar colunas necessárias
        required_columns = {'data', 'valor total', 'nº ped/ os/ prq', 'vendedor', 'cliente'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            flash(f'A planilha está faltando as seguintes colunas: {", ".join(missing_columns)}', 'error')
            return

        # Converter e limpar dados
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        df['valor total'] = pd.to_numeric(df['valor total'], errors='coerce')
        df['nº ped/ os/ prq'] = df['nº ped/ os/ prq'].astype(str)
        df['vendedor'] = df['vendedor'].astype(str)
        df['cliente'] = df['cliente'].astype(str)

        # Remover linhas onde qualquer das colunas principais é NaN
        df = df.dropna(subset=['data', 'valor total', 'nº ped/ os/ prq', 'vendedor', 'cliente'])

        # Filtrar pedidos da Comagro
        comagro_terms = ['comagro', 'comagro oficina', 'comagro peças e serviços']
        df = df[~df['cliente'].str.lower().str.contains('|'.join(comagro_terms), na=False)]

        conn = get_db_connection()
        cursor = conn.cursor()

        # Obter vendedores do banco de dados
        cursor.execute('SELECT id, name FROM Users WHERE role = "seller"')
        sellers = cursor.fetchall()
        sellers_dict = {remove_accents(seller['name'].lower()): seller['id'] for seller in sellers}

        for index, row in df.iterrows():
            vendedor_nome = remove_accents(row['vendedor'].lower())
            if vendedor_nome not in sellers_dict:
                continue
            user_id = sellers_dict[vendedor_nome]

            # Verificar se o pedido já existe
            cursor.execute('SELECT id, date FROM Sales WHERE order_number = ?', (row['nº ped/ os/ prq'],))
            existing_sales = cursor.fetchall()

            if existing_sales:
                # Atualizar o pedido se a data for mais recente
                for sale in existing_sales:

                    if row['data'] >= datetime.datetime.strptime(sale['date'], '%Y-%m-%d'):
                        cursor.execute('DELETE FROM Sales WHERE id = ?', (sale['id'],))
                cursor.execute('''
                    INSERT INTO Sales (date, amount, user_id, order_number)
                    VALUES (?, ?, ?, ?)
                ''', (row['data'].strftime('%Y-%m-%d'), row['valor total'], user_id, row['nº ped/ os/ prq']))
            else:
                cursor.execute('''
                    INSERT INTO Sales (date, amount, user_id, order_number)
                    VALUES (?, ?, ?, ?)
                ''', (row['data'].strftime('%Y-%m-%d'), row['valor total'], user_id, row['nº ped/ os/ prq']))

        conn.commit()

        cursor.execute('''
            SELECT order_number, MAX(date) as latest_date
            FROM Sales
            GROUP BY order_number
            HAVING COUNT(*) > 1
        ''')
        duplicate_sales = cursor.fetchall()

        for sale in duplicate_sales:
            cursor.execute('''
                DELETE FROM Sales
                WHERE order_number = ? AND date < ?
            ''', (sale['order_number'], sale['latest_date']))

        conn.commit()
        conn.close()

        flash('Planilha processada com sucesso!', 'success')
    except Exception as e:
        flash(f'Ocorreu um erro ao processar o arquivo: {e}', 'error')


# Rota para definir metas


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

        if not individual_goal and not general_goal:
            flash('Preencha pelo menos um dos campos de metas.', 'error')
            return redirect(request.url)

        # Atualizar ou inserir meta individual
        if individual_goal:
            cursor.execute('SELECT * FROM IndividualGoals WHERE user_id = ?', (user_id,))
            if cursor.fetchone():
                cursor.execute('UPDATE IndividualGoals SET goal = ? WHERE user_id = ?', (individual_goal, user_id))
            else:
                cursor.execute('INSERT INTO IndividualGoals (user_id, goal) VALUES (?, ?)', (user_id, individual_goal))

        # Atualizar meta geral (apenas uma entrada)
        if general_goal:
            cursor.execute('SELECT * FROM GeneralGoals')
            if cursor.fetchone():
                cursor.execute('UPDATE GeneralGoals SET goal = ? WHERE id = 1', (general_goal,))
            else:
                cursor.execute('INSERT INTO GeneralGoals (goal) VALUES (?)', (general_goal,))

        conn.commit()

        flash('Metas atualizadas com sucesso!', 'success')
        return redirect(url_for('set_goals'))

    # Buscar a meta geral atual
    cursor.execute('SELECT goal FROM GeneralGoals ORDER BY id DESC LIMIT 1')
    general_goal_row = cursor.fetchone()
    general_goal = general_goal_row['goal'] if general_goal_row else 0

    # Buscar vendedores e suas metas individuais
    cursor.execute('SELECT id, username FROM Users WHERE role = "seller"')
    sellers = cursor.fetchall()

    cursor.execute('SELECT user_id, goal FROM IndividualGoals')
    individual_goals = cursor.fetchall()
    individual_goals_dict = {goal['user_id']: goal['goal'] for goal in individual_goals}

    # Garantir que todos os vendedores tenham um valor de meta, mesmo que seja 0
    for seller in sellers:
        if seller['id'] not in individual_goals_dict:
            individual_goals_dict[seller['id']] = 0

    conn.close()
    return render_template('set_goals.html', sellers=sellers,
                           general_goal=general_goal,
                           individual_goals=individual_goals_dict)

# Adicionar o filtro de formatação de moeda


def format_currency(value):
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def format_percentage(value):
    return f'{value:,.2f}%'.replace(',', 'X').replace('X', '.')

# Rota para download do template de vendas


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])


app.jinja_env.filters['currency'] = format_currency
app.jinja_env.filters['percentage'] = format_percentage


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
