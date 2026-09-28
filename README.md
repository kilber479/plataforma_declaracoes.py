# Plataforma de Declarações de Encerramento

Página web interna onde a equipe envia a planilha e baixa as declarações prontas.

## Instalação (uma vez, no computador que vai hospedar a plataforma)

    python -m pip install -r requirements.txt

## Ligar a plataforma

Dê dois cliques em **INICIAR_PLATAFORMA.bat** (ou rode `python -m streamlit run app.py`).

- Neste computador: abra http://localhost:8501
- Colegas na mesma rede: usem o endereço **Network URL** que aparece na janela
  (algo como http://192.168.0.15:8501)
- Na primeira vez o Windows pode perguntar sobre o Firewall: permita em **redes privadas**.
- A plataforma fica no ar enquanto a janela estiver aberta e o computador ligado.

## Usando

1. **Gerar declarações:** envie a planilha, confira a empresa e as colunas reconhecidas,
   veja a conferência de dados faltando e clique em Gerar. Baixe o .zip.
2. **Empresas:** cadastre (com busca automática na Receita) ou edite empresas.
3. **Modelo:** baixe, edite no Word e envie de volta o texto da declaração.
   O modelo anterior fica guardado em `modelo/backup`.

Junto das declarações vem o **Relatorio.xlsx**, com resumo, lista de tudo que
foi gerado e as pendências. Uma cópia fica em `Saida/<empresa>/` (exceto na nuvem).

## Senha de acesso (opcional)

Renomeie `.streamlit/secrets.toml.exemplo` para `.streamlit/secrets.toml`,
troque a senha dentro dele e reinicie a plataforma.

## Publicar na nuvem (Streamlit Community Cloud)

1. Envie todos os arquivos desta pasta para um repositório **privado** no GitHub.
2. Em share.streamlit.io, crie o app apontando para `app.py`.
3. Em Advanced settings > Secrets, cole o conteúdo de `.streamlit/secrets.toml.exemplo`
   com a senha trocada.

### Cadastros permanentes

Com a parte `[github]` configurada nos Secrets, empresas cadastradas/editadas e
modelos enviados pelo site são gravados no ramo `dados` do repositório e
voltam sozinhos quando o app reinicia. O histórico de cada alteração fica no GitHub.
Sem essa configuração, as alterações feitas pelo site se perdem ao reiniciar.

O token precisa ser do tipo fine-grained, com acesso só a este repositório
e permissão **Contents: Read and write**.

## Uso pelo terminal (continua funcionando)

    python main.py            processa as planilhas da pasta Planilha/
    python main.py --vigiar   fica vigiando a pasta
    python main.py --pdf      também gera PDF

## PDF

A opção de PDF usa o Word (instale `python -m pip install docx2pdf pywin32`)
ou o LibreOffice, instalados no computador que roda a plataforma.
