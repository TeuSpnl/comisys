from flask import Blueprint, render_template, redirect, url_for, session
from ..db import get_db_connection
from datetime import datetime

dashboards_bp = Blueprint('dashboards', __name__)

# Rota para dashboard geral


@dashboards_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('users.login'))

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

        cursor.execute('SELECT branch FROM Users WHERE user_id = ?', (user_id,))
        user_branch_row = cursor.fetchone()
        user_branch = user_branch_row['goal'] if user_branch_row else 'N/A'

        conn.close()

        individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
        company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0

        if user_branch.upper() == 'LOJA':
            # Calcular a comissão com base nas metas individuais atingidas
            commission_rate = 0.01
            bonus_rate = 0
            if total_sales >= 225000:
                bonus_rate += 0.006
            elif total_sales >= 170000:
                bonus_rate += 0.004
            elif total_sales >= 130000:
                bonus_rate += 0.003
        elif user_branch.upper() == 'OFICINA':
            commission_rate = .5
            bonus_rate = 0
            if total_sales >= 50000:
                commission_rate += 0.05

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


@dashboards_bp.route('/dashboard/<int:seller_id>')
def seller_dashboard(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

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
    cursor.execute('''SELECT name, branch FROM Users WHERE id = ?''', (seller_id,))
    seller = cursor.fetchall()[0]

    print(seller['branch'])
    print('Type: ', type(seller))

    seller_branch = seller['branch']

    conn.close()

    individual_percentage = (total_sales / individual_goal) * 100 if individual_goal else 0
    company_percentage = (total_company_sales / general_goal) * 100 if general_goal else 0
    if seller_branch.upper() == 'LOJA':
        # Calcular a comissão com base nas metas individuais atingidas
        commission_rate = 0.01
        bonus_rate = 0
        if total_sales >= 225000:
            bonus_rate += 0.006
        elif total_sales >= 170000:
            bonus_rate += 0.004
        elif total_sales >= 130000:
            bonus_rate += 0.003
    elif seller_branch.upper() == 'OFICINA':
        commission_rate = .5
        bonus_rate = 0
        if total_sales >= 50000:
            commission_rate += 0.05

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
        username=seller['name'],
        individual_goal=individual_goal)
