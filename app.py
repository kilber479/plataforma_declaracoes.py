import io
import os
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

import streamlit as st

from src.empresa import (
    CAMPOS, PASTA_EMPRESAS, carregar_empresa, consultar_cnpj, identificar_empresa,
    listar_empresas, salvar_empresa,
)
from src.gerador import ROTULOS, conferir, gerar
from src.leitura_planilha import carregar_aba, detectar_aba, filtrar_linhas_validas, mapear_colunas
from src.utils import formatar_cnpj, formatar_data, nome_arquivo_seguro, normalizar

MODELO = Path("modelo/declaracao.docx")
NAO_USAR = "(não usar)"

st.set_page_config(page_title="Declarações de Encerramento", page_icon="📄", layout="wide")


def configuracao(chave, padrao=None):
    try:
        return st.secrets.get(chave, padrao)
    except Exception:
        return padrao


def senha_configurada():
    return configuracao("senha")


def exigir_login():
    senha = senha_configurada()
    if not senha or st.session_state.get("autenticado"):
        return True
    st.title("📄 Declarações de Encerramento")
    digitada = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar", type="primary"):
        if digitada == senha:
            st.session_state.autenticado = True
            st.rerun()
        st.error("Senha incorreta.")
    return False


def nome_empresa(caminho):
    return carregar_empresa(caminho).get("empresa", {}).get("nome", caminho.stem)


def salvar_upload(arquivo):
    chave = f"{arquivo.name}_{arquivo.size}"
    if st.session_state.get("upload_chave") != chave:
        pasta = Path(tempfile.mkdtemp(prefix="declaracoes_"))
        caminho = pasta / arquivo.name
        caminho.write_bytes(arquivo.getvalue())
        st.session_state.upload_chave = chave
        st.session_state.upload_caminho = caminho
        st.session_state.candidatos = detectar_aba(caminho)
        st.session_state.pop("resultado", None)
    return chave, st.session_state.upload_caminho


def compactar(pasta):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(pasta))
    return memoria.getvalue()


def pagina_gerar():
    st.title("📄 Gerar declarações")
    st.caption("Envie a planilha, confira o que foi reconhecido e baixe as declarações.")

    arquivo = st.file_uploader("Planilha de empreendimentos (.xlsx)", type=["xlsx", "xlsm"])
    if not arquivo:
        st.info("Envie uma planilha para começar.")
        return

    try:
        chave, caminho = salvar_upload(arquivo)
    except Exception as erro:
        st.error(f"Não consegui ler esta planilha: {erro}")
        return

    candidatos = st.session_state.candidatos
    abas = [aba for _, aba, _ in candidatos]
    cabecalho_por_aba = {aba: linha for _, aba, linha in candidatos}

    st.subheader("1. Planilha")
    c1, c2 = st.columns([3, 1])
    aba = c1.selectbox("Aba com os dados", abas, index=0, key=f"aba_{chave}")
    linha_cab = c2.number_input(
        "Linha do cabeçalho", min_value=1, max_value=50,
        value=cabecalho_por_aba[aba] + 1, key=f"cab_{chave}_{aba}",
    ) - 1

    try:
        dados, colunas = carregar_aba(caminho, aba, linha_cab)
    except Exception as erro:
        st.error(f"Erro ao ler a aba '{aba}': {erro}")
        return

    automatico = mapear_colunas(colunas)
    opcoes = [NAO_USAR] + colunas

    with st.expander("Colunas reconhecidas (clique para conferir ou corrigir)",
                     expanded=not all(automatico.get(c) for c in ("NOME_EMPREENDIMENTO", "CNPJ_EMPREENDIMENTO"))):
        mapa = {}
        grade = st.columns(4)
        for i, (campo, rotulo) in enumerate(ROTULOS.items()):
            padrao = automatico.get(campo)
            escolha = grade[i % 4].selectbox(
                rotulo, opcoes, index=opcoes.index(padrao) if padrao in opcoes else 0,
                key=f"col_{chave}_{aba}_{linha_cab}_{campo}",
            )
            mapa[campo] = None if escolha == NAO_USAR else escolha

    if not mapa["NOME_EMPREENDIMENTO"]:
        st.error("Escolha qual coluna tem o nome do empreendimento.")
        return

    dados = filtrar_linhas_validas(dados, mapa["NOME_EMPREENDIMENTO"])
    if dados.empty:
        st.error("Nenhum empreendimento encontrado com essas configurações.")
        return

    st.subheader("2. Empresa")
    chave_empresa = f"{chave}_{aba}_{mapa['CNPJ_EMPREENDIMENTO']}"
    if st.session_state.get("empresa_chave") != chave_empresa:
        with st.spinner("Identificando a empresa..."):
            st.session_state.empresa_detectada = identificar_empresa(dados, mapa["CNPJ_EMPREENDIMENTO"])
        st.session_state.empresa_chave = chave_empresa

    empresas = listar_empresas()
    detectada = st.session_state.empresa_detectada
    if not empresas:
        st.warning("Nenhuma empresa cadastrada. Cadastre na página **Empresas**, no menu ao lado.")
        return

    indice = empresas.index(detectada) if detectada in empresas else None
    if detectada:
        st.success(f"Empresa identificada pelo CNPJ: **{nome_empresa(detectada)}**")
    else:
        st.warning("Não consegui identificar a empresa pelos CNPJs da planilha. Escolha abaixo "
                   "ou cadastre-a na página **Empresas**.")
    escolhida = st.selectbox(
        "Empresa declarante", empresas, index=indice,
        format_func=nome_empresa, placeholder="Escolha a empresa", key=f"emp_{chave_empresa}",
    )
    if not escolhida:
        return
    config = carregar_empresa(escolhida)
    e = config["empresa"]
    st.caption(f"{e.get('nome')} · CNPJ {e.get('cnpj')} · {e.get('endereco')}, "
               f"{e.get('cidade')}-{e.get('uf')} · Assinatura em {e.get('cidade_assinatura') or e.get('cidade')}")

    st.subheader("3. Conferência")
    faltando, repetidos = conferir(dados, mapa, linha_cab)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Empreendimentos", len(dados))
    m2.metric("Completos", len(dados) - len(faltando))
    m3.metric("Com dados faltando", len(faltando))
    m4.metric("Nomes repetidos", len(repetidos))

    liberado = True
    if faltando:
        st.warning("Algumas linhas estão com dados faltando. Corrija a planilha e envie de novo, "
                   "ou gere assim mesmo (os campos faltando ficam em branco no documento).")
        st.dataframe(faltando, width="stretch", hide_index=True)
        liberado = st.checkbox("Estou ciente e quero gerar mesmo assim", key=f"ok_{chave_empresa}")
    if repetidos:
        st.info("Há empreendimentos com o nome repetido na planilha. Todos serão gerados; "
                "as repetições recebem um número no nome do arquivo.")
        st.dataframe(repetidos, width="stretch", hide_index=True)
    if not faltando and not repetidos:
        st.success("Todos os empreendimentos estão com os dados completos.")

    st.subheader("4. Gerar")
    o1, o2, o3 = st.columns(3)
    data_escolhida = o1.date_input("Data da declaração", value=date.today(), format="DD/MM/YYYY")
    formato = o2.radio("Formato da data", ["21/09/2026", "21 de setembro de 2026"], horizontal=True)
    com_pdf = o3.checkbox("Gerar também em PDF")

    if st.button("Gerar declarações", type="primary", disabled=not liberado, width="stretch"):
        data_texto = formatar_data(data_escolhida, extenso=formato != "21/09/2026")
        carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        nome_pasta = f"{nome_arquivo_seguro(Path(arquivo.name).stem)}_{carimbo}"
        if configuracao("guardar_copia", True):
            pasta = Path("Saida") / escolhida.stem / nome_pasta
        else:
            pasta = Path(tempfile.mkdtemp(prefix="saida_")) / nome_pasta

        barra = st.progress(0.0, text="Gerando...")
        gerados, avisos = gerar(
            dados, mapa, config, MODELO, pasta, data_texto, linha_cab,
            ao_progredir=lambda n, total, nome: barra.progress(n / total, text=f"{n}/{total} · {nome}"),
        )
        if com_pdf:
            barra.progress(1.0, text="Convertendo para PDF (pode levar alguns minutos)...")
            from src.gerador_pdf import converter_pasta
            converter_pasta(pasta, pasta / "PDF")
        barra.empty()

        config["colunas"] = {k: v for k, v in mapa.items() if v}
        salvar_empresa(config, escolhida.stem)

        st.session_state.resultado = {
            "zip": compactar(pasta),
            "nome_zip": f"Declaracoes_{escolhida.stem}_{carimbo}.zip",
            "quantidade": len(gerados),
            "pdfs": len(list((pasta / "PDF").glob("*.pdf"))) if com_pdf else None,
            "avisos": avisos,
            "chave": chave_empresa,
        }
        if not configuracao("guardar_copia", True):
            shutil.rmtree(pasta.parent, ignore_errors=True)

    resultado = st.session_state.get("resultado")
    if resultado and resultado["chave"] == chave_empresa:
        texto = f"{resultado['quantidade']} declarações geradas."
        if resultado["pdfs"] is not None:
            texto += f" {resultado['pdfs']} PDFs."
            if resultado["pdfs"] < resultado["quantidade"]:
                st.warning("Nem todos os PDFs foram gerados. Verifique se o Word ou o LibreOffice "
                           "está instalado no computador que roda a plataforma.")
        st.success(texto)
        st.download_button("⬇️ Baixar declarações (.zip)", resultado["zip"], resultado["nome_zip"],
                           mime="application/zip", type="primary", width="stretch")
        if resultado["avisos"]:
            with st.expander(f"Avisos ({len(resultado['avisos'])})"):
                for aviso in resultado["avisos"]:
                    st.write(f"- {aviso}")


def formulario_empresa(dados, chave):
    valores = {}
    c1, c2 = st.columns(2)
    for i, (campo, rotulo) in enumerate(CAMPOS):
        coluna = c1 if i % 2 == 0 else c2
        valores[campo] = coluna.text_input(rotulo, value=dados.get(campo, ""), key=f"{chave}_{campo}")
    valores["cnpj"] = formatar_cnpj(valores["cnpj"])
    valores["uf"] = valores["uf"].upper().strip()
    return valores


def pagina_empresas():
    st.title("🏢 Empresas")
    st.caption("Dados da empresa declarante que aparecem na declaração.")

    aba_editar, aba_nova = st.tabs(["Empresas cadastradas", "Cadastrar nova"])

    with aba_editar:
        empresas = listar_empresas()
        if not empresas:
            st.info("Nenhuma empresa cadastrada ainda.")
        else:
            escolhida = st.selectbox("Empresa", empresas, format_func=nome_empresa)
            config = carregar_empresa(escolhida)
            with st.form(f"editar_{escolhida.stem}"):
                valores = formulario_empresa(config.get("empresa", {}), f"ed_{escolhida.stem}")
                if st.form_submit_button("Salvar alterações", type="primary"):
                    config["empresa"] = valores
                    salvar_empresa(config, escolhida.stem)
                    st.success("Alterações salvas.")
            with st.expander("Excluir esta empresa"):
                if st.checkbox("Confirmo que quero excluir", key=f"del_{escolhida.stem}"):
                    if st.button("Excluir", type="secondary"):
                        escolhida.unlink()
                        st.rerun()

    with aba_nova:
        c1, c2 = st.columns([3, 1])
        cnpj = c1.text_input("CNPJ da matriz")
        c2.write("")
        c2.write("")
        if c2.button("Buscar na Receita", width="stretch"):
            with st.spinner("Consultando..."):
                encontrado = consultar_cnpj(cnpj)
            if encontrado:
                encontrado["cidade_assinatura"] = encontrado.get("cidade", "")
                st.session_state.nova_empresa = encontrado
                st.session_state.nova_versao = st.session_state.get("nova_versao", 0) + 1
                st.success("Dados encontrados. Confira abaixo antes de salvar.")
            else:
                st.error("Não foi possível consultar. Preencha os dados manualmente.")

        base = st.session_state.get("nova_empresa", {"cnpj": formatar_cnpj(cnpj)})
        with st.form("nova_empresa"):
            valores = formulario_empresa(base, f"nova_{st.session_state.get('nova_versao', 0)}")
            if st.form_submit_button("Cadastrar empresa", type="primary"):
                if not valores["nome"] or not valores["cnpj"]:
                    st.error("Preencha pelo menos o nome e o CNPJ.")
                else:
                    apelido = normalizar(valores["nome"].split()[0]).lower() or "empresa"
                    if (PASTA_EMPRESAS / f"{apelido}.json").exists():
                        apelido = f"{apelido}_{normalizar(valores['cnpj'])[:8]}"
                    salvar_empresa({"empresa": valores}, apelido)
                    st.session_state.pop("nova_empresa", None)
                    st.success(f"Empresa {valores['nome']} cadastrada.")


def pagina_modelo():
    st.title("📝 Modelo da declaração")
    st.caption("O texto base usado em todas as declarações.")

    st.download_button("⬇️ Baixar modelo atual", MODELO.read_bytes(), "declaracao.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    st.markdown("""
Para mudar o texto: baixe o modelo, edite no Word **mantendo os marcadores** entre chaves e envie de volta.

**Empresa:** `{{EMPRESA_NOME}}` `{{EMPRESA_CNPJ}}` `{{EMPRESA_ENDERECO}}` `{{EMPRESA_CIDADE}}`
`{{EMPRESA_UF}}` `{{EMPRESA_CEP}}` `{{CIDADE_ASSINATURA}}`

**Empreendimento:** `{{NOME_EMPREENDIMENTO}}` `{{CNPJ_EMPREENDIMENTO}}` `{{ENDERECO}}`
`{{COMPLEMENTO}}` `{{BAIRRO}}` `{{MUNICIPIO}}` `{{UF}}` `{{CEP}}`

**Geral:** `{{DATA}}`
""")

    novo = st.file_uploader("Enviar novo modelo (.docx)", type=["docx"])
    if novo and st.button("Substituir modelo", type="primary"):
        from docx import Document
        try:
            texto = "\n".join(p.text for p in Document(io.BytesIO(novo.getvalue())).paragraphs)
        except Exception:
            st.error("Esse arquivo não parece ser um documento do Word válido.")
            return
        if "{{NOME_EMPREENDIMENTO}}" not in texto:
            st.error("O modelo precisa ter pelo menos o marcador {{NOME_EMPREENDIMENTO}}.")
            return
        backup = MODELO.parent / "backup"
        backup.mkdir(exist_ok=True)
        shutil.copy(MODELO, backup / f"declaracao_{datetime.now():%Y-%m-%d_%H%M%S}.docx")
        MODELO.write_bytes(novo.getvalue())
        st.success("Modelo substituído. O anterior foi guardado em modelo/backup.")


if exigir_login():
    with st.sidebar:
        st.header("Menu")
        pagina = st.radio("Ir para", ["Gerar declarações", "Empresas", "Modelo"], label_visibility="collapsed")
        if senha_configurada() and st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    if pagina == "Gerar declarações":
        pagina_gerar()
    elif pagina == "Empresas":
        pagina_empresas()
    else:
        pagina_modelo()
