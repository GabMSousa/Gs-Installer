# GS Installer

## Desenvolvimento

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

## Build portátil

Execute `.\build.ps1`. O resultado é `dist\GSInstaller.exe`, um executável único gerado pelo PyInstaller.

## Organização portátil

Ao lado do executável, a aplicação cria `cache\`, `scripts\winscript\`, `logs\` e `config.json`. A pasta local padrão de instaladores é `D:\Ferramentas\Instaladores`, mas pode ser alterada em Configuração e não é obrigatória.

## Limites de segurança

Sites que não oferecem um asset direto estável são abertos como fonte oficial para download manual. Isso evita raspar páginas ou executar um arquivo de origem incerta. Hash SHA-256 pode ser calculado pelo serviço de download quando a integração de metadados for adicionada.

WinScript e a desinstalação profunda exigem revisão humana: leia a prévia dos scripts e confirme os candidatos residuais antes de habilitar remoção forçada.
