# GS Installer / NiniteTool

## Stack escolhida

Python 3.11+ com PySide6 e PyInstaller. O PySide6 foi mantido porque a primeira versão funcional já possui uma UI nativa Windows, temas claro/escuro, navegação por teclado e menor risco de migração durante a execução das tarefas. O PyInstaller gera um único `.exe` portátil.

## Arquitetura

- `src/core/`: contratos dos serviços de instalação, download/cache, desinstalação e WinScript.
- `src/gui/`: limites das telas de instalação, limpeza e desinstalação.
- `src/utils/`: configuração, logs e helpers compartilhados.
- `src/data/apps_catalog.json`: catálogo declarativo com categorias e URLs oficiais.
- `scripts/winscript/`: scripts obtidos do repositório oficial após o primeiro uso.
- `cache/`: downloads e arquivos intermediários reutilizáveis.
- `logs/`: logs diários da execução.
- `app/`: implementação funcional atual, compartilhada pelos módulos de `src/`.

O `Downloader` grava downloads em um arquivo temporário, valida tamanho, calcula SHA-256 e só então publica o arquivo no cache. Artefatos existentes são reutilizados, salvo quando `force=True`; falhas de rede usam até três tentativas com timeout configurável e reportam progresso em bytes.

## Desenvolvimento

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

Também é possível iniciar pelo layout solicitado:

```powershell
python -m src.main
```

## Configuração inicial

`config.json` usa `D:\Ferramentas\Instaladores` como facilitador, mas a pasta pode ser alterada pela aplicação e não é obrigatória. O catálogo só aponta para fontes oficiais.

## Build

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GSInstaller app/main.py
```

O executável será criado em `dist\GSInstaller.exe`.
