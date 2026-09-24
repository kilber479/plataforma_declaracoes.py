from src.empresa import substituicoes_empresa
from src.preenchimento import preencher_modelo, marcadores_restantes
from src.utils import formatar_cnpj, nome_arquivo_seguro

CAMPOS_CONFERIDOS = ["CNPJ_EMPREENDIMENTO", "ENDERECO", "BAIRRO", "MUNICIPIO", "CEP"]

ROTULOS = {
    "NOME_EMPREENDIMENTO": "Nome do empreendimento",
    "CNPJ_EMPREENDIMENTO": "CNPJ do empreendimento",
    "ENDERECO": "Endereço",
    "COMPLEMENTO": "Complemento",
    "BAIRRO": "Bairro",
    "MUNICIPIO": "Município",
    "UF": "UF",
    "CEP": "CEP",
}


def valor(linha, mapa, campo):
    coluna = mapa.get(campo)
    return str(linha[coluna]).strip() if coluna else ""


def linha_excel(indice, linha_cabecalho):
    return indice + linha_cabecalho + 2


def conferir(dados, mapa, linha_cabecalho):
    faltando, repetidos = [], []
    vistos = {}
    for indice, linha in dados.iterrows():
        numero = linha_excel(indice, linha_cabecalho)
        nome = valor(linha, mapa, "NOME_EMPREENDIMENTO")
        vazios = [ROTULOS[c] for c in CAMPOS_CONFERIDOS if not valor(linha, mapa, c)]
        if vazios:
            faltando.append({"Linha": numero, "Empreendimento": nome, "Falta": ", ".join(vazios)})
        chave = nome_arquivo_seguro(nome)
        if chave in vistos:
            vistos[chave]["vezes"] += 1
            repetidos.append({
                "Linha": numero,
                "Empreendimento": nome,
                "Aviso": f"Repetido (também na linha {vistos[chave]['linha']}). "
                         f"Será salvo como '{chave} ({vistos[chave]['vezes']})'",
            })
        else:
            vistos[chave] = {"linha": numero, "vezes": 1}
    return faltando, repetidos


def gerar(dados, mapa, config, modelo, pasta_saida, data_declaracao, linha_cabecalho,
          remover_destaque=True, ao_progredir=None):
    pasta_saida.mkdir(parents=True, exist_ok=True)
    empresa = config["empresa"]
    fixos = substituicoes_empresa(config)
    fixos["{{DATA}}"] = data_declaracao

    usados, avisos, gerados = {}, [], []
    total = len(dados)

    for posicao, (indice, linha) in enumerate(dados.iterrows(), 1):
        numero_linha = linha_excel(indice, linha_cabecalho)
        nome = valor(linha, mapa, "NOME_EMPREENDIMENTO")

        substituicoes = dict(fixos)
        substituicoes.update({
            "{{NOME_EMPREENDIMENTO}}": nome,
            "{{CNPJ_EMPREENDIMENTO}}": formatar_cnpj(valor(linha, mapa, "CNPJ_EMPREENDIMENTO")),
            "{{ENDERECO}}": valor(linha, mapa, "ENDERECO"),
            "{{COMPLEMENTO}}": valor(linha, mapa, "COMPLEMENTO"),
            "{{BAIRRO}}": valor(linha, mapa, "BAIRRO"),
            "{{MUNICIPIO}}": valor(linha, mapa, "MUNICIPIO"),
            "{{UF}}": valor(linha, mapa, "UF") or empresa.get("uf", ""),
            "{{CEP}}": valor(linha, mapa, "CEP"),
        })

        vazios = [ROTULOS[c] for c in CAMPOS_CONFERIDOS if not valor(linha, mapa, c)]
        if vazios:
            avisos.append(f"Linha {numero_linha} ({nome}): sem {', '.join(vazios)}")

        base = nome_arquivo_seguro(nome) or f"linha_{numero_linha}"
        usados[base] = usados.get(base, 0) + 1
        if usados[base] > 1:
            avisos.append(f"Linha {numero_linha}: '{nome}' repetido, salvo como '{base} ({usados[base]})'")
            base = f"{base} ({usados[base]})"

        caminho = pasta_saida / f"{base}.docx"
        preencher_modelo(modelo, caminho, substituicoes, remover_destaque=remover_destaque)
        gerados.append(caminho)

        if ao_progredir:
            ao_progredir(posicao, total, nome)

    if gerados:
        sobras = marcadores_restantes(gerados[0])
        if sobras:
            avisos.insert(0, f"Marcadores do modelo sem dado: {', '.join(sobras)}")

    if avisos:
        (pasta_saida / "avisos.txt").write_text("\n".join(avisos), encoding="utf-8")

    return gerados, avisos
