$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt
python build.py
Write-Host "Build concluído em dist\NiniteTool\NiniteTool.exe"
