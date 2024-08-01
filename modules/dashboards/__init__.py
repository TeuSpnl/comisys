from flask import Blueprint, render_template, redirect, url_for, session, flash
from ..db import get_db_connection
from datetime import datetime

dashboards_bp = Blueprint('dashboards', __name__)

# Rota para dashboard geral


@dashboards_bp.route('/dashboard', defaults={'seller_id': None})
@dashboards_bp.route('/dashboard/<int:seller_id>')
def dashboard(seller_id):
    if 'user_id' not in session:
        return redirect(url_for('users.login'))

    # Pegar informações do usuário logado
    user_id = session['user_id']
    user_role = session['role']

    # Conectar ao banco de dados
    conn = get_db_connection()
    cursor = conn.cursor()

    # Se o usuário for um vendedor, ele só pode ver o próprio dashboard
    if user_role == 'seller' or (user_role == 'master' and seller_id is None):
        seller_id = user_id

    # Pegar informações do vendedor
    cursor.execute('SELECT name, branch, active FROM Users WHERE id = ?', (seller_id,))
    user_info = cursor.fetchone()
    
    if not user_info or user_info['active'] == 0:
        flash('Usuário inativo ou não encontrado.', 'error')
        return redirect(url_for('users.login'))
    
    user_name = user_info['name']
    user_branch = user_info['branch']

    # Pegar vendas do vendedor
    cursor.execute('''
        SELECT SUM(amount) AS total_seller_sales 
        FROM Sales 
        WHERE user_id = ? 
        AND strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
    ''', (seller_id,))
    total_saleseller_s_row = cursor.fetchone()
    total_seller_sales = total_saleseller_s_row['total_seller_sales'] if total_saleseller_s_row and total_saleseller_s_row['total_seller_sales'] else 0

    # Pegar meta individual do vendedor
    cursor.execute('SELECT goal FROM IndividualGoals WHERE user_id = ?', (seller_id,))
    individual_goal_row = cursor.fetchone()
    individual_goal = individual_goal_row['goal'] if individual_goal_row else 0

    # Pegar vendas da filial do vendedor
    cursor.execute('''
        SELECT SUM(amount) AS total_branch_sales 
        FROM Sales 
        WHERE user_id IN (SELECT id FROM Users WHERE branch = ?) 
        AND strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
    ''', (user_branch,))
    total_branch_sales_row = cursor.fetchone()
    total_branch_sales = total_branch_sales_row['total_branch_sales'] if total_branch_sales_row and total_branch_sales_row['total_branch_sales'] else 0

    # Pegar meta geral
    cursor.execute('SELECT goal FROM GeneralGoals ORDER BY id DESC LIMIT 1')
    general_goal_row = cursor.fetchone()
    general_goal = float(general_goal_row['goal']) if general_goal_row else 0

    # Pegar vendas do vendedor
    cursor.execute('''
        SELECT date, amount, order_number, id 
        FROM Sales 
        WHERE user_id = ? 
        AND strftime('%m', date) = strftime('%m', 'now') 
        AND strftime('%Y', date) = strftime('%Y', 'now')
        ORDER BY order_number DESC
    ''', (seller_id,))
    vendas = cursor.fetchall()

    # Calcular porcentagens individuais e da filial
    individual_percentage = (total_seller_sales / individual_goal) * 100 if individual_goal else 0
    branch_percentage = (total_branch_sales / general_goal) * 100 if general_goal else 0

    # Setar a taxa comissão e bônus da loja
    if user_branch == 'Loja':
        commission_rate = 0.01
        bonus_rate = 0
        if total_seller_sales >= 225000:
            bonus_rate = 0.006
        elif total_seller_sales >= 170000:
            bonus_rate = 0.004
        elif total_seller_sales >= 130000:
            bonus_rate = 0.003
    # Setar a taxa comissão da oficina
    elif user_branch == 'Oficina':
        bonus_rate = 0
        commission_rate = 0.005
        if total_branch_sales >= 500000:
            commission_rate = 0.01
        

    commission = total_seller_sales * commission_rate
    bonus = total_seller_sales * bonus_rate
    
    extra_total = commission + bonus

    if user_role == 'seller' or (user_role == 'master' and seller_id != user_id):
        conn.close()
        return render_template('seller_dashboard.html',
                               total_seller_sales=total_seller_sales,
                               total_branch_sales=total_branch_sales,
                               individual_percentage=individual_percentage,
                               branch_percentage=branch_percentage,
                               user_id=user_id,
                               user_name=user_name,
                               general_goal=general_goal,
                               vendas=vendas,
                               individual_goal=individual_goal,
                               commission=commission,
                               bonus=bonus,
                               extra_total=extra_total,
                               user_branch=user_branch,
                               user_role=user_role)

    elif user_role == 'master':
        cursor.execute('SELECT id, username, name FROM Users WHERE role = "seller" AND active = 1')
        sellers = cursor.fetchall()

        cursor.execute('''
            SELECT SUM(amount) AS total_sales 
            FROM Sales 
            WHERE strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''')
        total_sales_row = cursor.fetchone()
        total_sales = total_sales_row['total_sales'] if total_sales_row and total_sales_row['total_sales'] else 0

        cursor.execute('''
            SELECT SUM(amount) AS total_store_sales 
            FROM Sales 
            WHERE user_id IN (SELECT id FROM Users WHERE branch = 'Loja') 
            AND strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''')
        total_store_sales_row = cursor.fetchone()
        total_store_sales = total_store_sales_row['total_store_sales'] if total_store_sales_row and total_store_sales_row['total_store_sales'] else 0

        cursor.execute('''
            SELECT SUM(amount) AS total_workshop_sales 
            FROM Sales 
            WHERE user_id IN (SELECT id FROM Users WHERE branch = 'Oficina') 
            AND strftime('%m', date) = strftime('%m', 'now') 
            AND strftime('%Y', date) = strftime('%Y', 'now')
        ''')
        total_workshop_sales_row = cursor.fetchone()
        total_workshop_sales = total_workshop_sales_row[
            'total_workshop_sales'] if total_workshop_sales_row and total_workshop_sales_row['total_workshop_sales'] else 0

        conn.close()

        return render_template('master_dashboard.html',
                               sellers=sellers,
                               general_goal=general_goal,
                               total_sales=total_sales,
                               total_store_sales=total_store_sales,
                               total_workshop_sales=total_workshop_sales,
                               user_role=user_role)
