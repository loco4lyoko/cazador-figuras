@echo off
REM Revisa Goofish desde tu notebook (Goofish bloquea los servidores en la nube).
cd /d "%~dp0.."
python -m cazador.main --solo goofish --datos notebook\datos_goofish.json >> notebook\registro.txt 2>&1
