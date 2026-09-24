import pandas as pd

from src.utils import normalizar

SINONIMOS = {
    "NOME_EMPREENDIMENTO": ["NOME DO EMPREENDIMENTO", "EMPREENDIMENTO", "NOME EMPREENDIMENTO",
                            "NOME DA OBRA", "RESIDENCIAL", "NOME"],
    "CNPJ_EMPREENDIMENTO": ["CNPJ AFETAÇÃO", "CNPJ AFETACAO", "CNPJ DO EMPREENDIMENTO",
                            "CNPJ EMPREENDIMENTO", "CNPJ DA OBRA", "CNPJ SPE", "CNPJ"],
    "ENDERECO": ["ENDEREÇO", "ENDERECO", "LOGRADOURO", "RUA", "ENDEREÇO DA OBRA"],
    "COMPLEMENTO": ["COMPLEMENTO", "COMPL", "LOTE QUADRA", "LOTE/QUADRA"],
    "BAIRRO": ["BAIRRO", "DISTRITO"],
    "MUNICIPIO": ["MUNICÍPIO", "MUNICIPIO", "CIDADE"],
    "UF": ["UF", "ESTADO"],
    "CEP": ["CEP", "CÓDIGO POSTAL"],
}

OBRIGATORIOS = ["NOME_EMPREENDIMENTO", "CNPJ_EMPREENDIMENTO", "ENDERECO", "MUNICIPIO"]


def _achar_coluna(colunas, sinonimos):
    normalizadas = {normalizar(c): c for c in colunas}
    for s in sinonimos:
        if normalizar(s) in normalizadas:
            return normalizadas[normalizar(s)]
    for s in sinonimos:
        ns = normalizar(s)
        if len(ns) < 6:
            continue
        for nc, original in normalizadas.items():
            if ns in nc:
                return original
    return None


def mapear_colunas(colunas, mapeamento_fixo=None):
    mapeamento_fixo = mapeamento_fixo or {}
    mapa = {}
    for campo, sinonimos in SINONIMOS.items():
        if mapeamento_fixo.get(campo) in colunas:
            mapa[campo] = mapeamento_fixo[campo]
        else:
            mapa[campo] = _achar_coluna(colunas, sinonimos)
    return mapa


def _pontuar(colunas):
    mapa = mapear_colunas(colunas)
    return sum(1 for v in mapa.values() if v)


def _detectar_cabecalho(bruto, max_linhas=20):
    melhor, melhor_pontos = 0, -1
    for i in range(min(max_linhas, len(bruto))):
        valores = [str(v) for v in bruto.iloc[i].tolist() if pd.notna(v)]
        pontos = _pontuar(valores)
        if pontos > melhor_pontos:
            melhor, melhor_pontos = i, pontos
    return melhor, melhor_pontos


def detectar_aba(caminho):
    resultados = []
    with pd.ExcelFile(caminho) as arquivo:
        for aba in arquivo.sheet_names:
            bruto = pd.read_excel(arquivo, sheet_name=aba, header=None, dtype=str, nrows=25)
            linha, pontos = _detectar_cabecalho(bruto)
            resultados.append((pontos, aba, linha))
    resultados.sort(reverse=True)
    return resultados


def carregar_aba(caminho, aba, linha_cabecalho):
    dados = pd.read_excel(caminho, sheet_name=aba, header=linha_cabecalho, dtype=str).fillna("")
    dados.columns = [str(c).strip() for c in dados.columns]
    dados = dados.loc[:, ~dados.columns.duplicated()]
    colunas = [c for c in dados.columns if not c.startswith("Unnamed")]
    return dados, colunas


def filtrar_linhas_validas(dados, coluna_nome):
    return dados[dados[coluna_nome].astype(str).str.strip() != ""]


def perguntar_coluna(campo, colunas):
    print(f"\n Não encontrei automaticamente a coluna para: {campo}")
    for i, c in enumerate(colunas, 1):
        print(f"   {i:>2}. {c}")
    print("    0. (deixar em branco no documento)")
    while True:
        r = input(" Número da coluna: ").strip()
        if r.isdigit() and 0 <= int(r) <= len(colunas):
            return None if r == "0" else colunas[int(r) - 1]
        print(" Opção inválida.")


def ler_planilha(caminho, aba=None, linha_cabecalho=None, mapeamento_fixo=None, interativo=True):
    if aba is None:
        candidatos = detectar_aba(caminho)
        pontos, aba, linha_detectada = candidatos[0]
        empate = [c for c in candidatos if c[0] == pontos]
        if len(empate) > 1 and interativo:
            print("\nMais de uma aba parece conter os dados:")
            for i, (_, nome, _) in enumerate(empate, 1):
                print(f"   {i}. {nome}")
            r = input(" Qual usar? ").strip()
            if r.isdigit() and 1 <= int(r) <= len(empate):
                _, aba, linha_detectada = empate[int(r) - 1]
        if linha_cabecalho is None:
            linha_cabecalho = linha_detectada

    if linha_cabecalho is None:
        bruto = pd.read_excel(caminho, sheet_name=aba, header=None, dtype=str, nrows=25)
        linha_cabecalho, _ = _detectar_cabecalho(bruto)

    dados, colunas = carregar_aba(caminho, aba, linha_cabecalho)

    mapa = mapear_colunas(colunas, mapeamento_fixo)

    if interativo:
        for campo in OBRIGATORIOS:
            if not mapa.get(campo):
                mapa[campo] = perguntar_coluna(campo, colunas)

    if not mapa.get("NOME_EMPREENDIMENTO"):
        raise ValueError("Não foi possível identificar a coluna com o nome do empreendimento.")

    dados = filtrar_linhas_validas(dados, mapa["NOME_EMPREENDIMENTO"])

    print(f"\n Planilha: aba '{aba}', cabeçalho na linha {linha_cabecalho + 1} do Excel")
    print(f" {len(dados)} empreendimentos encontrados")
    print(" Colunas usadas:")
    for campo, coluna in mapa.items():
        print(f"   {campo:<22} <- {coluna or '(não encontrada, fica em branco)'}")

    return dados, mapa, aba, linha_cabecalho
