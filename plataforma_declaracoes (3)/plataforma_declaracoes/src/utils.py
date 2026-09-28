import re
import unicodedata


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def somente_digitos(texto):
    return re.sub(r"\D", "", str(texto))


def formatar_cnpj(cnpj):
    d = somente_digitos(cnpj)
    if len(d) != 14:
        return str(cnpj).strip()
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def formatar_cep(cep):
    d = somente_digitos(cep)
    if len(d) != 8:
        return str(cep).strip()
    return f"{d[:2]}.{d[2:5]}-{d[5:]}"


def _digito_cnpj(base):
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
    soma = sum(int(n) * p for n, p in zip(base, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_matriz(cnpj_qualquer):
    d = somente_digitos(cnpj_qualquer)
    if len(d) < 8:
        return None
    base = d[:8] + "0001"
    base += _digito_cnpj(base)
    base += _digito_cnpj(base)
    return formatar_cnpj(base)


def nome_arquivo_seguro(nome):
    for c in '<>:"/\\|?*':
        nome = nome.replace(c, "")
    return re.sub(r"\s+", " ", nome).strip().rstrip(".")


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def formatar_data(data, extenso=False):
    if extenso:
        return f"{data.day} de {MESES[data.month - 1]} de {data.year}"
    return data.strftime("%d/%m/%Y")
