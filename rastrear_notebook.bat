@echo off
REM Revisa desde tu notebook los sitios que bloquean a GitHub (Goofish, Suruga-ya, Off Mall, Lashinbang, AmiAmi).
cd /d "%~dp0.."
python -m cazador.main --solo goofish,surugaya,offmall,lashinbang,amiami --datos notebook\datos_notebook.json >> notebook\registro.txt 2>&1
