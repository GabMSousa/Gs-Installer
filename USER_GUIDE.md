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

## Instalação silenciosa

Ao iniciar um lote, a aplicação confirma a quantidade selecionada e executa o trabalho em segundo plano. A barra superior mostra programas concluídos; a segunda mostra o download atual quando a fonte informa o tamanho. O log registra horário, origem do instalador, saída do processo e resumo final.

MSI usa `msiexec /qn /norestart`. Instaladores EXE usam argumentos por fornecedor, como `/S`, `/silent /install`, `/quiet` ou `/VERYSILENT /NORESTART`. Alguns fornecedores podem ignorar esses argumentos ou exigir interação; nesses casos a execução é registrada como falha e não bloqueia os próximos itens do lote. Prefira instaladores offline/standalone quando o fornecedor oferecer essa opção.

## WinScript

Na aba Limpeza, o repositório oficial é baixado para `scripts/winscript/` somente quando ainda não há scripts locais. A estrutura original é preservada e a execução funciona offline depois disso. Selecione um script para ver a prévia, confirme o aviso de segurança e use Cancelar para impedir o próximo script; o script atualmente em execução pode precisar encerrar antes que o cancelamento seja efetivo.
