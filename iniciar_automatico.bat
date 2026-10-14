@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Radar Tributario - modo automatico (nao feche esta janela)
python radar_fiscal.py --agendar
