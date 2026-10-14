@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Buscando noticias... (leva de 3 a 6 minutos)
python radar_fiscal.py
echo.
echo Concluido! Abrindo o painel...
start "" "index.html"
pause
