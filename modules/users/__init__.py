from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from ..db import get_db_connection

users_bp = Blueprint('users', __name__)


# Rota para registro de usuários
@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboards.dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']
        branch = request.form['branch']

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Users (username, password, name, role, branch) VALUES (?, ?, ?, ?, ?)',
                       (username, hashed_password, name, role, branch))
        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!', 'success')

    return render_template('register.html')

# Rota para deletar vendedores


@users_bp.route('/delete_user/<int:seller_id>', methods=['POST'])
def delete_user(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboards.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Users WHERE id = ?', (seller_id,))
    conn.commit()
    conn.close()

    flash('Vendedor deletado com sucesso!', 'success')
    return redirect(url_for('dashboards.dashboard'))

# Rotas para atualizar senha de usuários


@users_bp.route('/update_password/<int:seller_id>', methods=['GET', 'POST'])
def update_password(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE Users SET password = ? WHERE id = ? AND role = "seller"', (hashed_password, seller_id))
        conn.commit()
        conn.close()

        flash('Senha do vendedor atualizada com sucesso!', 'success')
        return redirect(url_for('dashboards.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM Users WHERE id = ? AND role = "seller"', (seller_id,))
    seller = cursor.fetchone()
    conn.close()

    if not seller:
        flash('Vendedor não encontrado!', 'error')
        return redirect(url_for('dashboards.dashboard'))

    return render_template('update_password.html', seller=seller)

# Rota para login


@users_bp.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('dashboards.dashboard'))
        else:
            flash('Login inválido, verifique suas credenciais.', 'error')

    return render_template('login.html')

# Rota para logout


@users_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('users.login'))
