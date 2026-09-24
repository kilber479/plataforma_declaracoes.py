import json
import urllib.request
from collections import Counter
from pathlib import Path

from src.utils import cnpj_matriz, formatar_cnpj, normalizar, somente_digitos

PASTA_EMPRESAS = Path("config/empresas")

CAMPOS = [
    ("nome", "Nome da empresa (razão social)"),
    ("cnpj", "CNPJ da matriz"),
    ("endereco", "Endereço (rua, número, complemento/bairro)"),
    ("cidade", "Cidade da matriz"),
    ("uf", "UF da matriz"),
    ("cep", "CEP da matriz"),
    ("cidade_assinatura", "Cidade que aparece na data/assinatura"),
]


def listar_empresas():
    PASTA_EMPRESAS.mkdir(parents=True, exist_ok=True)
    return sorted(PASTA_EMPRESAS.glob("*.json"))


def carregar_empresa(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def salvar_empresa(config, apelido):
    PASTA_EMPRESAS.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_EMPRESAS / f"{apelido}.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return caminho


def consultar_cnpj(cnpj):
    url = f"https://brasilapi.com.br/api/cnpj/v1/{somente_digitos(cnpj)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gerador-declaracoes"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except Exception as erro:
        print(f"   (não foi possível consultar o CNPJ online: {erro})")
        return None

    logradouro = " ".join(
        p for p in [d.get("descricao_tipo_de_logradouro"), d.get("logradouro")] if p
    ).strip()
    partes = [logradouro, d.get("numero"), d.get("complemento"), d.get("bairro")]
    endereco = ", ".join(str(p).strip() for p in partes if p and str(p).strip())

    return {
        "nome": d.get("razao_social", ""),
        "cnpj": formatar_cnpj(d.get("cnpj", cnpj)),
        "endereco": endereco,
        "cidade": str(d.get("municipio", "")).title(),
        "uf": d.get("uf", ""),
        "cep": somente_digitos(d.get("cep", "")),
    }


def sugerir_cnpj_matriz(dados, coluna_cnpj):
    if not coluna_cnpj:
        return None
    raizes = [somente_digitos(c)[:8] for c in dados[coluna_cnpj] if len(somente_digitos(c)) == 14]
    if not raizes:
        return None
    raiz = Counter(raizes).most_common(1)[0][0]
    return cnpj_matriz(raiz)


def cadastrar_empresa(dados=None, coluna_cnpj=None):
    print("\n" + "=" * 60)
    print(" CADASTRO DE NOVA EMPRESA")
    print("=" * 60)

    sugestao = {}
    cnpj_sugerido = sugerir_cnpj_matriz(dados, coluna_cnpj) if dados is not None else None
    if cnpj_sugerido:
        print(f"\n Pelos CNPJs da planilha, a matriz parece ser: {cnpj_sugerido}")
        r = input(" Está correto? [S/n] ou digite outro CNPJ: ").strip()
        cnpj = cnpj_sugerido if r.lower() in ("", "s", "sim") else r
    else:
        cnpj = input("\n CNPJ da matriz: ").strip()

    print(" Consultando dados do CNPJ...")
    sugestao = consultar_cnpj(cnpj) or {"cnpj": formatar_cnpj(cnpj)}
    sugestao.setdefault("cidade_assinatura", sugestao.get("cidade", ""))

    print("\n Confira os dados (Enter mantém o valor entre colchetes):")
    config = {}
    for chave, rotulo in CAMPOS:
        atual = sugestao.get(chave, "")
        if chave == "cidade_assinatura" and not atual:
            atual = config.get("cidade", "")
        r = input(f"   {rotulo} [{atual}]: ").strip()
        config[chave] = r or atual

    config["cnpj"] = formatar_cnpj(config["cnpj"])
    config["uf"] = config["uf"].upper()

    apelido_padrao = normalizar(config["nome"].split()[0] if config["nome"] else "empresa").lower()
    apelido = input(f"\n Apelido para salvar este cadastro [{apelido_padrao}]: ").strip() or apelido_padrao
    apelido = normalizar(apelido).lower()

    caminho = salvar_empresa({"empresa": config}, apelido)
    print(f"\n Empresa salva em {caminho}")
    return caminho


def escolher_empresa(dados=None, coluna_cnpj=None):
    empresas = listar_empresas()
    if empresas:
        print("\n Empresas cadastradas:")
        for i, e in enumerate(empresas, 1):
            nome = carregar_empresa(e).get("empresa", {}).get("nome", "")
            print(f"   {i}. {e.stem:<15} {nome}")
        print("   0. Cadastrar nova empresa")
        while True:
            r = input(" Escolha: ").strip()
            if r == "0":
                break
            if r.isdigit() and 1 <= int(r) <= len(empresas):
                return empresas[int(r) - 1]
            print(" Opção inválida.")
    return cadastrar_empresa(dados, coluna_cnpj)


def substituicoes_empresa(config):
    e = config["empresa"]
    return {
        "{{EMPRESA_NOME}}": e.get("nome", ""),
        "{{EMPRESA_CNPJ}}": e.get("cnpj", ""),
        "{{EMPRESA_ENDERECO}}": e.get("endereco", ""),
        "{{EMPRESA_CIDADE}}": e.get("cidade", ""),
        "{{EMPRESA_UF}}": e.get("uf", ""),
        "{{EMPRESA_CEP}}": e.get("cep", ""),
        "{{CIDADE_ASSINATURA}}": e.get("cidade_assinatura", "") or e.get("cidade", ""),
    }


def identificar_empresa(dados, coluna_cnpj):
    matriz = sugerir_cnpj_matriz(dados, coluna_cnpj)
    if not matriz:
        print(" Não encontrei CNPJs válidos na planilha para identificar a empresa.")
        return None
    raiz = somente_digitos(matriz)[:8]

    for caminho in listar_empresas():
        cnpj_salvo = carregar_empresa(caminho).get("empresa", {}).get("cnpj", "")
        if somente_digitos(cnpj_salvo)[:8] == raiz:
            print(f" Empresa reconhecida pelo CNPJ: cadastro '{caminho.stem}'")
            return caminho

    print(f" Empresa nova (matriz {matriz}). Consultando a Receita...")
    dados_receita = consultar_cnpj(matriz)
    if not dados_receita or not dados_receita.get("nome"):
        return None

    dados_receita["cidade_assinatura"] = dados_receita.get("cidade", "")
    apelido = normalizar(dados_receita["nome"].split()[0]).lower() or raiz
    if (PASTA_EMPRESAS / f"{apelido}.json").exists():
        apelido = f"{apelido}_{raiz}"
    caminho = salvar_empresa({"empresa": dados_receita}, apelido)
    print(f" Cadastrada automaticamente: {dados_receita['nome']} -> {caminho}")
    print("   (confira/edite esse arquivo se algum dado precisar de ajuste)")
    return caminho
