@echo off
title Cubic CLI - Windows Mode
echo Verificando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Erro ao instalar dependencias. Verifique se o Python e o Pip estao no PATH.
    pause
    exit /b
)
echo Iniciando Cubic...
python main.py
pause
