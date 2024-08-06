from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from ..db import get_db_connection

users_bp = Blueprint('users', __name__)

# Rota para a tela de usuários


@users_bp.route('/users')
def users():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Users')
    users = cursor.fetchall()
    conn.close()

    return render_template('users.html', users=users)


# Rota para registro de usuários
@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboards.dashboard'))

    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        name = request.form['name'].title()
        role = request.form['role']
        branch = request.form['branch']
        active = 1 if 'active' in request.form else 0

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verificar se o pedido já existe
        cursor.execute('SELECT name, username FROM Users WHERE lower(username) = ? OR lower(name) = ?', (username, name))
        existing_users = cursor.fetchall()

        if existing_users:
            for user in existing_users:
                if user['username'].lower() == username:
                    flash('Usuário já cadastrado!', 'error')
                    return render_template('register.html')
                if user['name'].title() == name:
                    flash(f'Nome já cadastrado! Username: {user["username"]}', 'error')
                    return render_template('register.html')
        else:
            cursor.execute('INSERT INTO Users (username, password, name, role, branch, active) VALUES (?, ?, ?, ?, ?, ?)',
                           (username, hashed_password, name, role, branch, active))
        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!', 'success')

    return render_template('register.html')


# Rota para deletar vendedores


@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('dashboards.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    if session['user_id'] == user_id:
        return redirect(url_for('users.logout'))

    flash('Usuário deletado com sucesso!', 'success')
    return redirect(url_for('users.users'))

# Rotas para atualizar senha de usuários


@users_bp.route('/update_password/<int:user_id>', methods=['GET', 'POST'])
def update_password(user_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE Users SET password = ? WHERE id = ?', (hashed_password, user_id))
        conn.commit()
        conn.close()

        if session['user_id'] == user_id:
            return redirect(url_for('users.logout'))

        flash('Senha atualizada com sucesso!', 'success')
        return redirect(url_for('users.users'))

# Rota para atualizar a filial de um usuário


@users_bp.route('/update_branch/<int:user_id>', methods=['POST'])
def update_branch(user_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    new_branch = request.form['new_branch']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE Users SET branch = ? WHERE id = ?', (new_branch, user_id))
    conn.commit()
    conn.close()

    flash('Filial atualizada com sucesso!', 'success')
    return redirect(url_for('users.users'))


@users_bp.route('/update_status/<int:user_id>', methods=['POST'])
def update_status(user_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))
    
    new_status = int(request.form['new_status'])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE Users SET active = ? WHERE id = ?', (new_status, user_id))
    conn.commit()
    conn.close()
    
    flash('Status atualizado com sucesso!', 'success')
    return redirect(url_for('users.users'))

# Rota para login


@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Users WHERE lower(username) = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            if not user['active']:
                flash('Usuário inativo, entre em contato com o administrador.', 'error')
                return render_template('login.html')
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
