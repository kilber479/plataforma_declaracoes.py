@echo off
cd /d "%~dp0"
echo Iniciando a plataforma...
echo.
echo Neste computador: http://localhost:8501
echo Para os colegas: use o endereco "Network URL" que aparece abaixo.
echo Para desligar, feche esta janela.
echo.
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
