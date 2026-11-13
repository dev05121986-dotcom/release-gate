# Release Gate

CLI Python 3.11+ que confere um checklist local antes de uma release.
Os comandos não modificam os arquivos do projeto.

## Checklist provisório

Execute na pasta que contém `release-gate.toml`:

```toml
schema_version = 1

[checklist]
readme = "README.md"
changelog = "CHANGELOG.md"
license = "LICENSE"
junit = "artifacts/junit.xml"
```

As quatro chaves são obrigatórias; campos desconhecidos, tipos incorretos e
caminhos vazios são rejeitados. Esta configuração substitui a tabela provisória
`[changelog]` da implementação inicial; o envelope JSON mantém schema_version 1.
A ordem dos resultados é README, changelog, licença e JUnit.

Todos os caminhos devem ser relativos à pasta do projeto (diretório atual).
Antes de inspecionar cada item, a CLI resolve seu caminho e rejeita caminhos
absolutos, escapes com `..` e links simbólicos que apontem para fora da pasta.
Subpastas e links para arquivos dentro do projeto são aceitos. A verificação
pressupõe que os caminhos não mudem concorrentemente durante a execução.

O changelog precisa ser um arquivo regular UTF-8 com texto além de espaços.
README, licença e JUnit precisam apenas ser arquivos regulares: conteúdo vazio é
aceito. O JUnit não é interpretado; sua presença confirma apenas que existe um
arquivo de relatório. **O pytest determina se os testes passaram.** Um relatório
com falhas ou XML inválido não reprova esse check de presença.

## Instalação e testes no Linux Mint

Na raiz do projeto, com Python 3.11 ou superior e suporte a venv instalados:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest --junitxml=artifacts/junit.xml
```

O último comando gera o relatório e retorna um erro se os testes falharem.
Não use o Release Gate para substituir esse resultado.

Após gerar o JUnit com os testes aprovados, os comandos abaixo devem retornar
`0`, pois a raiz contém README, changelog e licença MIT:

```bash
release-gate check
release-gate check --json
```

## Demonstração reproduzível

As duas pastas em `examples/` diferem apenas pela presença de `CHANGELOG.md`.
Os arquivos `LICENSE` nelas são textos explicitamente ilustrativos e não
licenciam este projeto. O JUnit versionado é uma amostra ilustrativa.

Na raiz, com o ambiente virtual ativado, execute em Bash:

```bash
(
  set -euo pipefail
  python -m pytest --junitxml=artifacts/junit.xml
  bash scripts/demo.sh 2>&1 | tee artifacts/demo-terminal.log
)
```

A demonstração só começa depois de o pytest passar. O script cria cópias
temporárias dos exemplos, usa nelas o relatório real do pytest e remove as
cópias ao terminar. Os arquivos ilustrativos originais permanecem intactos.
Ele executa texto e JSON nos dois cenários, imprime os códigos reais e exige
exatamente `0` com changelog e `1` sem changelog. Qualquer divergência encerra
a demonstração com erro. O próprio script retorna `0` quando os quatro códigos
estão corretos, inclusive a reprovação esperada do exemplo sem changelog.

O log completo fica em `artifacts/demo-terminal.log`, que é ignorado pelo Git.
Para capturar uma sessão interativa do terminal no Linux Mint, use `script`
(util-linux), após ativar o ambiente virtual:

```bash
mkdir -p artifacts
script -q -e artifacts/terminal-session.log
# Dentro da sessão de gravação:
python -m pytest --junitxml=artifacts/junit.xml && bash scripts/demo.sh
exit
```

O comando `exit` encerra a gravação. O primeiro cenário aprova os quatro itens;
o segundo lista apenas `changelog_missing` como falha. Para executar cada CLI
manualmente com os arquivos ilustrativos e ver o código de retorno:

```bash
(cd examples/with-changelog; release-gate check; printf 'exit_code=%s\n' "$?")
(cd examples/without-changelog; release-gate check; printf 'exit_code=%s\n' "$?")
```

## Arquivos locais e preparação do commit

`.gitignore` exclui `.venv`, caches, metadados de instalação, builds, `/artifacts/`
(relatórios reais, logs, cópias temporárias e diff de revisão), `review.diff`,
configurações locais de ferramentas/editores e arquivos `.env`. Os relatórios
ilustrativos em `examples/*/artifacts/junit.xml` permanecem versionáveis.
Antes de preparar o commit em um repositório Git inicializado, confira
`git status --short --untracked-files=all` e `git diff --cached --name-only`.

## Contrato da CLI

- `0`: todos os checks aprovados.
- `1`: algum arquivo ausente, changelog vazio ou item comum que não é arquivo regular.
- `2`: erro de uso, configuração, caminho ou acesso/leitura; tem precedência sobre `1`.

`release-gate check` escreve os checks aprovados/reprovados em stdout e os erros
operacionais em stderr. Todos os arquivos ausentes são listados juntos, mesmo
quando outro item tem erro. O resumo é APROVADO, REPROVADO ou ERRO.

`release-gate check --json` escreve um único objeto JSON e uma quebra de linha em
stdout; stderr permanece vazio para erros tratados. O envelope contém
`schema_version`, `status` (`passed`, `failed`, `error`), `checks` e `errors`.
Cada check contém `id`, `status`, `code`, `path` e `message`. Erros de item também
aparecem em `errors`, com `id`, `path`, `code` e `message`. Erros de configuração
têm apenas `code` e `message`, com `checks` vazio. Ajuda e argumentos inválidos
seguem o comportamento convencional do argparse, inclusive com `--json`.

Códigos estáveis para automação:

- `<item>_valid` e `<item>_missing`, para os quatro identificadores do checklist.
- `<item>_not_regular`, para readme, license e junit.
- `changelog_empty` e `changelog_read_error` (inclui diretório, FIFO e UTF-8 inválido).
- `<item>_path_invalid` e `<item>_read_error`, para erros de caminho e acesso.
- `config_missing`, `config_invalid` e `config_read_error`.

## GitHub Actions

`.github/workflows/ci.yml` instala o pacote e roda o pytest em Python 3.11 e 3.12.
O relatório JUnit é gerado antes da demonstração. Uma falha no pytest encerra a
sequência: o gate não transforma testes reprovados em sucesso. O workflow chama `scripts/demo.sh` após o pytest passar, usa cópias temporárias
dos exemplos e exige código `0` com changelog e `1` sem changelog, em texto e JSON. Ele usa as pastas de demonstração para não atribuir
uma licença provisória ao projeto real.

O workflow está preparado para push, pull request e execução manual; a execução
remota aguarda criação do repositório e autorização para publicação.

## Licença

Release Gate é distribuído sob a [licença MIT](LICENSE).
Copyright (c) 2026 Carlos dos Santos Souza.
Os arquivos LICENSE dos exemplos são ilustrativos e permanecem inalterados.
