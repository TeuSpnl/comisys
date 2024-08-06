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

    # Processar a planilha de vendas
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        # Abre o arquivo enviado
        file = request.files['file']

        # Verificar se o arquivo é válido
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        # Se o arquivo for válido, processar
        if file:
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                file_path = temp_file.name
                file.save(file_path)

            # Tenta processar o arquivo
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
        # Ler a planilha
        df = pd.read_excel(file_path, header=None)

        # Identificar a linha inicial da tabela
        start_row = None
        for i, row in df.iterrows():
            if 'data' in row.astype(str).str.lower().tolist():
                start_row = i
                break

        # Se não encontrar a linha inicial, exibir mensagem de erro
        if start_row is None:
            flash('Não foi possível identificar a linha inicial da tabela.', 'error')
            return

        # Ler a planilha novamente, pulando as linhas iniciais
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

        # Iniciar a conexão com o banco de dados
        conn = get_db_connection()
        cursor = conn.cursor()

        # Marcar todas as vendas do mês atual como não processadas
        current_year = datetime.now().year
        current_month = datetime.now().month
        cursor.execute('''
            UPDATE Sales 
            SET processed = 0 
            WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
        ''', (current_year, current_month))

        # Obter vendedores do banco de dados
        cursor.execute('SELECT id, name FROM Users')
        sellers = cursor.fetchall()
        sellers_dict = {remove_accents(seller['name'].title()): seller['id'] for seller in sellers}

        # Set para armazenar vendedores não cadastrados
        non_registered_sellers = set()

        # Inserir vendas na tabela Sales
        for index, row in df.iterrows():
            seller_name = remove_accents(row['vendedor'].title())
            user_id = sellers_dict.get(seller_name, None)  # Pode ser None se o vendedor não estiver cadastrado

            if user_id is None and seller_name not in non_registered_sellers:
                non_registered_sellers.add(seller_name)
                flash(f'Vendedor {row["vendedor"].title()} não cadastrado.', 'warning')

            order_number = row['nº ped/ os/ prq']
            sale_amount = row['valor total']

            # Verifica se o pedido já existe no banco de dados
            cursor.execute('SELECT id, amount FROM Sales WHERE order_number = ?', (order_number,))
            existing_order = cursor.fetchone()

            if existing_order:
                # Se o pedido existe, atualiza o valor do pedido
                new_amount = existing_order['amount'] + sale_amount
                if new_amount <= 0:
                    cursor.execute('DELETE FROM Sales WHERE id = ?', (existing_order['id'],))
                else:
                    cursor.execute('UPDATE Sales SET amount = ?, processed = 1 WHERE id = ?',
                                   (new_amount, existing_order['id']))
            else:
                # Insere a venda no banco de dados
                cursor.execute('''
                    INSERT INTO Sales (date, amount, user_id, order_number, processed)
                    VALUES (?, ?, ?, ?, 1)
                ''', (row['data'].strftime('%Y-%m-%d'), sale_amount, user_id, order_number))

        # Apagar vendas do mês atual que não foram processadas (consideradas devoluções totais)
        cursor.execute('''
            DELETE FROM Sales 
            WHERE processed = 0 
            AND strftime('%Y', date) = ? AND strftime('%m', date) = ?
        ''', (current_year, current_month))

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
