import base64
from pathlib import Path

import requests

API = "https://api.github.com"
ARQUIVOS_SINCRONIZADOS = ["config/empresas", "modelo/declaracao.docx"]


class ErroGitHub(Exception):
    pass


class ArmazenamentoGitHub:
    def __init__(self, token, repositorio, branch="dados"):
        self.repositorio = repositorio.strip().strip("/")
        self.branch = branch
        self.sessao = requests.Session()
        self.sessao.headers.update({
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _url(self, caminho=""):
        return f"{API}/repos/{self.repositorio}/{caminho}"

    def _requisitar(self, metodo, caminho, **kwargs):
        resposta = self.sessao.request(metodo, self._url(caminho), timeout=30, **kwargs)
        if resposta.status_code == 404:
            return None
        if resposta.status_code >= 400:
            try:
                mensagem = resposta.json().get("message", resposta.text)
            except ValueError:
                mensagem = resposta.text
            raise ErroGitHub(f"GitHub respondeu {resposta.status_code}: {mensagem}")
        return resposta.json() if resposta.content else {}

    def _conteudo(self, caminho):
        return self._requisitar("GET", f"contents/{caminho}", params={"ref": self.branch})

    def testar(self):
        if self._requisitar("GET", "") is None:
            raise ErroGitHub("Repositório não encontrado ou o token não tem acesso a ele.")

    def garantir_branch(self):
        if self._requisitar("GET", f"git/ref/heads/{self.branch}"):
            return False
        repo = self._requisitar("GET", "")
        principal = repo["default_branch"]
        ref = self._requisitar("GET", f"git/ref/heads/{principal}")
        self._requisitar("POST", "git/refs", json={
            "ref": f"refs/heads/{self.branch}", "sha": ref["object"]["sha"],
        })
        return True

    def baixar_arquivo(self, caminho, destino):
        info = self._conteudo(caminho)
        if not info or info.get("type") != "file":
            return False
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if info.get("content"):
            destino.write_bytes(base64.b64decode(info["content"]))
        else:
            blob = self._requisitar("GET", f"git/blobs/{info['sha']}")
            destino.write_bytes(base64.b64decode(blob["content"]))
        return True

    def baixar_pasta(self, caminho, destino):
        itens = self._conteudo(caminho)
        if not isinstance(itens, list):
            return 0
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        remotos = set()
        for item in itens:
            if item["type"] == "file":
                self.baixar_arquivo(item["path"], destino / item["name"])
                remotos.add(item["name"])
        for local in destino.iterdir():
            if local.is_file() and local.name not in remotos:
                local.unlink()
        return len(remotos)

    def enviar(self, caminho_local, caminho_remoto=None, mensagem=None):
        caminho_local = Path(caminho_local)
        caminho_remoto = (caminho_remoto or caminho_local.as_posix()).lstrip("./")
        atual = self._conteudo(caminho_remoto)
        corpo = {
            "message": mensagem or f"Atualiza {caminho_remoto}",
            "content": base64.b64encode(caminho_local.read_bytes()).decode("ascii"),
            "branch": self.branch,
        }
        if atual and atual.get("sha"):
            corpo["sha"] = atual["sha"]
        self._requisitar("PUT", f"contents/{caminho_remoto}", json=corpo)

    def excluir(self, caminho_remoto, mensagem=None):
        caminho_remoto = Path(caminho_remoto).as_posix().lstrip("./")
        atual = self._conteudo(caminho_remoto)
        if not atual:
            return
        self._requisitar("DELETE", f"contents/{caminho_remoto}", json={
            "message": mensagem or f"Remove {caminho_remoto}",
            "sha": atual["sha"],
            "branch": self.branch,
        })

    def sincronizar_para_local(self):
        self.garantir_branch()
        empresas = self.baixar_pasta("config/empresas", "config/empresas")
        self.baixar_arquivo("modelo/declaracao.docx", "modelo/declaracao.docx")
        return empresas
