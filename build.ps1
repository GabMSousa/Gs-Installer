$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GSInstaller app/main.py
Write-Host "Build concluído em dist\GSInstaller.exe"
