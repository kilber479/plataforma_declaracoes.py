import argparse
import gc
import os
import shutil
import sys
import time
from datetime import date, datetime
from pathlib import Path

from src.empresa import (
    cadastrar_empresa, carregar_empresa, escolher_empresa, identificar_empresa,
    salvar_empresa, substituicoes_empresa, PASTA_EMPRESAS,
)
from src.leitura_planilha import ler_planilha
from src.gerador import gerar
from src.utils import formatar_data, nome_arquivo_seguro

PASTA_ENTRADA = Path("Planilha")
PASTA_PROCESSADAS = PASTA_ENTRADA / "processadas"
PASTA_COM_ERRO = PASTA_ENTRADA / "com_erro"

def planilhas_pendentes():
    PASTA_ENTRADA.mkdir(exist_ok=True)
    return sorted(
        p for p in PASTA_ENTRADA.iterdir()
        if p.is_file()
        and p.suffix.lower() in (".xlsx", ".xlsm", ".xls")
        and not p.name.startswith("~$")
    )


def mover(arquivo, destino):
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / arquivo.name
    if alvo.exists():
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alvo = destino / f"{arquivo.stem}_{carimbo}{arquivo.suffix}"
    shutil.move(str(arquivo), str(alvo))
    return alvo


def processar_planilha(caminho_planilha, args, interativo=False):
    caminho_planilha = Path(caminho_planilha)
    print("\n" + "=" * 60)
    print(f" PLANILHA: {caminho_planilha.name}")
    print("=" * 60)

    caminho_empresa = None
    if args.empresa:
        caminho_empresa = Path(args.empresa)
        if caminho_empresa.suffix != ".json":
            caminho_empresa = PASTA_EMPRESAS / f"{args.empresa}.json"
        if not caminho_empresa.exists():
            print(f" Empresa não encontrada: {caminho_empresa}")
            return False
    config = carregar_empresa(caminho_empresa) if caminho_empresa else {}

    dados, mapa, aba, linha_cab = ler_planilha(
        caminho_planilha,
        aba=args.aba,
        mapeamento_fixo=config.get("colunas", {}),
        interativo=interativo,
    )

    if not caminho_empresa:
        caminho_empresa = identificar_empresa(dados, mapa.get("CNPJ_EMPREENDIMENTO"))
        if not caminho_empresa:
            if interativo:
                print("\n Não identifiquei a empresa automaticamente.")
                caminho_empresa = escolher_empresa(dados, mapa.get("CNPJ_EMPREENDIMENTO"))
            else:
                print(" Não consegui identificar a empresa desta planilha.")
                print(" Cadastre com:  python main.py --cadastrar")
                return False
        config = carregar_empresa(caminho_empresa)

    config["colunas"] = {k: v for k, v in mapa.items() if v}
    salvar_empresa(config, caminho_empresa.stem)

    empresa = config["empresa"]
    print(f"\n Empresa: {empresa['nome']} ({empresa['cnpj']})")

    data_declaracao = args.data or formatar_data(date.today(), args.data_extenso)
    pasta_saida = Path("Saida") / caminho_empresa.stem / nome_arquivo_seguro(caminho_planilha.stem)

    gerados, avisos = gerar(
        dados, mapa, config, args.modelo, pasta_saida, data_declaracao, linha_cab,
        remover_destaque=not args.manter_destaque,
    )

    print(f"\n {len(gerados)} declarações geradas em: {pasta_saida}")
    print(f" Data usada: {data_declaracao}")
    if avisos:
        print(f"\n ATENÇÃO ({len(avisos)}), veja também avisos.txt:")
        for a in avisos:
            print(f"  - {a}")

    if args.pdf:
        from src.gerador_pdf import converter_pasta
        converter_pasta(pasta_saida, pasta_saida / "PDF")

    return True


def processar_pendentes(args, interativo=False):
    pendentes = planilhas_pendentes()
    for planilha in pendentes:
        try:
            ok = processar_planilha(planilha, args, interativo=interativo)
        except Exception as erro:
            print(f"\n ERRO ao processar {planilha.name}: {erro}")
            ok = False

        gc.collect()
        destino_pasta = PASTA_PROCESSADAS if ok else PASTA_COM_ERRO
        for tentativa in range(3):
            try:
                destino = mover(planilha, destino_pasta)
                print(f" Planilha movida para: {destino}")
                break
            except PermissionError:
                time.sleep(1)
        else:
            print(f" Não consegui mover '{planilha.name}': ela está aberta em outro programa.")
            print(" Feche o Excel. Ela continua na pasta Planilha e será lida de novo na próxima vez.")
    return len(pendentes)


def arquivo_estavel(caminho, espera=2):
    try:
        tamanho = caminho.stat().st_size
        time.sleep(espera)
        return tamanho == caminho.stat().st_size and tamanho > 0
    except FileNotFoundError:
        return False


def vigiar(args, intervalo=5):
    print(f" Vigiando a pasta '{PASTA_ENTRADA}/'. Coloque planilhas lá.")
    print(" (Ctrl+C para parar)")
    while True:
        if any(arquivo_estavel(p) for p in planilhas_pendentes()):
            processar_pendentes(args)
            print(f"\n Vigiando a pasta '{PASTA_ENTRADA}/'...")
        time.sleep(intervalo)


def main():
    ap = argparse.ArgumentParser(description="Gera declarações a partir de planilhas.")
    ap.add_argument("--planilha", help="Processa um arquivo específico (sem mover)")
    ap.add_argument("--empresa", help="Força uma empresa cadastrada (apelido ou .json)")
    ap.add_argument("--aba", help="Força o nome da aba")
    ap.add_argument("--modelo", default="modelo/declaracao.docx")
    ap.add_argument("--data", help="Data da declaração (padrão: hoje)")
    ap.add_argument("--data-extenso", action="store_true")
    ap.add_argument("--pdf", action="store_true", help="Também gera PDFs")
    ap.add_argument("--manter-destaque", action="store_true")
    ap.add_argument("--vigiar", action="store_true", help="Fica rodando e processa planilhas novas")
    ap.add_argument("--cadastrar", action="store_true", help="Cadastra uma empresa manualmente")
    args = ap.parse_args()

    if args.cadastrar:
        cadastrar_empresa()
    elif args.planilha:
        processar_planilha(args.planilha, args, interativo=True)
    elif args.vigiar:
        vigiar(args)
    else:
        if processar_pendentes(args, interativo=sys.stdin.isatty()) == 0:
            print(f" Nenhuma planilha na pasta '{PASTA_ENTRADA}/'.")
            print(" Coloque o arquivo .xlsx lá e rode de novo.")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    try:
        main()
    except KeyboardInterrupt:
        print("\n Encerrado.")
