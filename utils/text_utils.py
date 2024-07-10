import unicodedata

# Filtros de formatação de texto

def format_currency(value):
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def format_percentage(value):
    return f'{value:,.2f}%'.replace(',', 'X').replace('X', '.')


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

