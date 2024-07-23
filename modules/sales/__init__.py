from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.text_utils import remove_accents
from ..db import get_db_connection
import pandas as pd
import tempfile
import datetime
import os


sales_bp = Blueprint('sales', __name__)


# Rota para upload de planilha
@sales_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                file_path = temp_file.name
                file.save(file_path)
            
            try:
                process_file(file_path)
            except Exception as e:
                flash(f'Erro ao processa a planilha: {e}', 'error')
            finally:
                os.remove(file_path)

    return render_template('upload.html')

# Função para processar a planilha de vendas


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
        
        # Limpar a tabela Sales antes de inserir novos dados
        cursor.execute('DELETE FROM Sales')

        # Obter vendedores do banco de dados
        cursor.execute('SELECT id, name FROM Users WHERE role = "seller"')
        sellers = cursor.fetchall()
        sellers_dict = {remove_accents(seller['name'].lower()): seller['id'] for seller in sellers}

        for index, row in df.iterrows():
            vendedor_nome = remove_accents(row['vendedor'].lower())
            user_id = sellers_dict.get(vendedor_nome, None)  # Pode ser None se o vendedor não estiver cadastrado

            order_number = row['nº ped/ os/ prq']
            
            cursor.execute('''
                INSERT INTO Sales (date, amount, user_id, order_number)
                VALUES (?, ?, ?, ?)
            ''', (row['data'].strftime('%Y-%m-%d'), row['valor total'], user_id, order_number))
            
            # try:
            #     int_ord_nb = int(float(order_number))
            #     if int_ord_nb > 100000:
            #         cursor.execute('''
            #             INSERT INTO Sales (date, amount, user_id, order_number)
            #             VALUES (?, ?, ?, ?)
            #         ''', (row['data'].strftime('%Y-%m-%d'), row['valor total'], user_id, order_number))
                    
            #         print(f'Inserindo pedido {order_number}')
            # except ValueError:
            #     cursor.execute('''
            #         INSERT INTO Sales (date, amount, user_id, order_number)
            #         VALUES (?, ?, ?, ?)
            #     ''', (row['data'].strftime('%Y-%m-%d'), row['valor total'], user_id, order_number))
            # except Exception as e:
            #     flash(f'Erro ao processar o pedido {order_number}: {e}, {e.__class__}', 'error')
            #     return
            
        conn.commit()
        conn.close()

        flash('Planilha processada com sucesso!', 'success')
    except Exception as e:
        flash(f'Ocorreu um erro ao processar o arquivo: {e}, {e.__class__}', 'error')


# Rota para deletar vendas

@sales_bp.route('/delete_sale/<int:sale_id>', methods=['POST'])
def delete_sale(sale_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Sales WHERE id = ?', (sale_id,))
    conn.commit()
    conn.close()

    flash('Venda deletada com sucesso!', 'success')
    return redirect(request.referrer)


@sales_bp.route('/delete_all_sales/<int:seller_id>', methods=['POST'])
def delete_all_sales(seller_id):
    if 'user_id' not in session or session['role'] != 'master':
        return redirect(url_for('users.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Sales WHERE user_id = ?', (seller_id,))
    conn.commit()
    conn.close()

    flash('Todas as vendas foram deletadas com sucesso!', 'success')
    return redirect(request.referrer)
