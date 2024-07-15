import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from modules.dashboards import dashboards_bp
from modules.sales import sales_bp
from modules.users import users_bp
from utils.text_utils import format_currency, format_percentage

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Registrar os blueprints
app.register_blueprint(dashboards_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(users_bp)


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
        role TEXT NOT NULL,  -- 'seller' ou 'master'
        branch TEXT NOT NULL  -- Filial do usuário
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
        user_id INTEGER,
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


# Rota para definir metas
@app.route('/set_goals', methods=['GET', 'POST'])
def set_goals():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

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


app.jinja_env.filters['currency'] = format_currency
app.jinja_env.filters['percentage'] = format_percentage


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
