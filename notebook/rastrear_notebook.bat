@echo off
REM Revisa desde tu notebook los sitios que bloquean a GitHub (Goofish, Suruga-ya, Off Mall, Lashinbang, AmiAmi).
REM Tambien revisa las preventas en GunDamit y eBay (monitor de preventas, tambien bloqueados en GitHub).
cd /d "%~dp0.."
git pull -q >> notebook\registro.txt 2>&1
python -m cazador.main --solo goofish,surugaya,offmall,lashinbang,amiami --datos notebook\datos_notebook.json >> notebook\registro.txt 2>&1
python -m cazador.preventas --notebook >> notebook\registro.txt 2>&1
