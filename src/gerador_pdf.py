import shutil
import subprocess
from pathlib import Path


def _achar_soffice():
    for nome in ("soffice", "libreoffice"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    padrao_windows = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    return str(padrao_windows) if padrao_windows.exists() else None


def converter_pasta(pasta_docx, pasta_pdf):
    pasta_docx, pasta_pdf = Path(pasta_docx), Path(pasta_pdf)
    pasta_pdf.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(pasta_docx.glob("*.docx"))
    if not arquivos:
        print(" Nenhum .docx para converter.")
        return

    try:
        from docx2pdf import convert
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        print(f"\n Convertendo {len(arquivos)} arquivos para PDF com o Word...")
        convert(str(pasta_docx), str(pasta_pdf))
        return
    except ImportError:
        pass
    except Exception as erro:
        print(f" docx2pdf falhou ({erro}); tentando LibreOffice...")

    soffice = _achar_soffice()
    if not soffice:
        print(" Para gerar PDF instale o docx2pdf (pip install docx2pdf, precisa do Word)")
        print(" ou o LibreOffice (https://www.libreoffice.org).")
        return

    print(f"\n Convertendo {len(arquivos)} arquivos para PDF com o LibreOffice...")
    resultado = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pasta_pdf)]
        + [str(a) for a in arquivos],
        check=False, capture_output=True,
    )

    gerados = len(list(pasta_pdf.glob("*.pdf")))
    if resultado.returncode != 0 or gerados < len(arquivos):
        print(f" Atenção: só {gerados} de {len(arquivos)} PDFs foram gerados.")
        print(" Se o LibreOffice estiver aberto, feche-o e tente de novo.")
    else:
        print(f" PDFs salvos em {pasta_pdf}")
