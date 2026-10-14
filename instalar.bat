@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando os componentes do Radar Tributario...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Pronto! Agora de dois cliques em "executar_radar.bat" para testar.
pause
