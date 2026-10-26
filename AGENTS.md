# AGENTS.md — guia para uma IA trabalhando neste repositório

Este arquivo existe para orientar uma IA (Claude, Copilot, etc.) a se mover
pelo projeto sem precisar reconstruir o contexto do zero a cada vez. Leia
isto antes de mexer em qualquer coisa.

## O que este projeto faz

É um analisador automático de pastas de documentos fiscais/societários
(contratos, CNPJ, QSA, certidões, faturamento...) de clientes do Studio
Fiscal. Dado o caminho de uma pasta de rede de um cliente (ex.:
`\\studiofiscal\Temporarios\001 - EMPRESA`), o sistema varre a estrutura de
subpastas esperada, extrai texto de PDFs/XLSX (com OCR como fallback para
PDF escaneado), roda uma lista fixa de "elementos de análise" (honorários,
data de abertura, simples nacional, sócios, faturamento médio, etc.) e monta
um checklist de alertas (sem contrato, faturamento baixo, com Regularize...).

O **core de negócio é 100% o script Python** (`services/analisar_job.py`) —
é ele que sabe onde procurar cada documento, como extrair cada dado e quais
são os limiares (R$ 20M/30M/50M, classes do Regularize etc.). Tudo o mais
no repo (Node, banco, build) é só **transporte e persistência** do que esse
script já decidiu. Se a tarefa for "mudar uma regra de negócio" (ex.: outro
limiar, outra pasta-alvo, outro padrão de nome de arquivo), o lugar certo é
quase sempre dentro de `ELEMENTOS` / `PROCESSADORES` em `analisar_job.py` —
não no lado Node.

⚠️ O analisador é **somente leitura**: nunca move, renomeia ou apaga
arquivos do cliente. Preserve essa garantia em qualquer mudança.

## Os dois modos de execução (não confunda os dois)

O projeto roda de **duas formas completamente diferentes**, compartilhando
só o analisador Python. Antes de mexer em algo, identifique em qual modo a
mudança se aplica — nem toda mudança vale para os dois.

### Modo API (VM) — `server.js`

Pensado para o time todo usar, com histórico centralizado.

```
PM2 → node server.js (porta 3030, fora do Docker)
         └─ spawn analisar_job.py/.exe por requisição
         └─ MySQL (dentro de um container Docker, só ele)
```

- `server.js` sobe o Express, registra as rotas e inicializa o banco.
- `routes/api.routes.js` → `controllers/job_pro.controller.js`: recebe
  `POST /api/jobs/analisar { pasta_raiz, num_job }`, chama o analisador via
  `child_process.spawn`, parseia o JSON que ele devolve no stdout, grava um
  JSON sidecar em `data/jobs/` e faz upsert na tabela `jobs_pro` do MySQL
  (chave única: `num_job`).
- `db/connection.js` usa **mysql2/promise** com um pool de conexões. A
  conexão é configurada por `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`
  (ver `.env.example`). Toda query no controller é `async/await` — não há
  chamada síncrona de banco neste modo (diferente de versões antigas do
  projeto que usavam SQLite síncrono — se você ver `better-sqlite3` ou
  `.prepare(...).get()/.run()` em algum lugar, é código desatualizado).
- O **MySQL roda em Docker** (`docker-compose.yml`), mas a **API roda fora
  do Docker**, gerenciada por **PM2** (`ecosystem.config.js`). Isso é
  proposital: a API precisa acessar compartilhamentos de rede Windows
  (`\\studiofiscal\...`) com as credenciais do usuário logado na VM, e isso
  não funcionava bem quando a API também estava containerizada.
- Setup inicial da VM: `init_vm.txt` (instala Node/Python/Tesseract/PM2,
  sobe o MySQL, cria `.env`, registra a tarefa agendada). Dia a dia:
  `start.ps1` (idempotente — garante Docker+PM2 no ar).
- Frontend estático em `frontend/index.html`, servido pelo próprio Express
  em `/` — consome `/api/jobs`, `/api/jobs/:id`, `/api/jobs/analisar`.

### Modo Desktop (GUI, Electron) — `desktop-gui/`

Pensado para um usuário rodar sozinho, sem depender de servidor nenhum,
numa **janela gráfica** com a mesma cara do dashboard do Modo API.

```
AnaliseDesktop.exe (Electron)
  └─ main.js sobe um Express LOCAL (loopback 127.0.0.1, porta escolhida
     pelo SO — nunca acessível de fora da máquina) e abre uma BrowserWindow
     carregando esse servidor
        └─ server/app.js     → monta as rotas + serve frontend/index.html
        └─ server/controller.js → spawn analisar_job.py/.exe (mesma lógica
           de detecção do Modo API: usa .exe empacotado se existir ao lado,
           senão cai pra python3 services/analisar_job.py)
        └─ server/jobStore.js → "banco" local em JSON (data/jobs.json, ao
           lado do executável), com upsert por num_job e escrita atômica
           (grava em .tmp e faz rename, pra nunca corromper o arquivo)
```

- `desktop-gui/frontend/index.html` é uma cópia literal de
  `frontend/index.html` (mesmo HTML/CSS/JS do Modo API) — é assim que a
  GUI desktop fica visualmente idêntica ao dashboard web. Qualquer mudança
  visual pedida "pros dois modos" precisa ser replicada nos dois arquivos
  (não há compartilhamento de template entre eles hoje).
- Cada instalação tem seu **próprio histórico local** — não há
  sincronização entre máquinas nem com o MySQL do Modo API. Isso é
  intencional: o usuário autorizou explicitamente um "banco" simples em
  arquivo (ver histórico de decisão) em vez de embutir um banco real
  (SQLite) dentro do Electron, para evitar o risco de módulos nativos
  (`better-sqlite3`) compilados pro ABI errado do Electron.
- `desktop-gui/package.json` tem `build:win` (`@electron/packager`, não o
  pacote `electron-packager` antigo/deprecado — mesmo binário de CLI,
  então os scripts não mudam) que gera
  `dist/build/AnaliseDesktop-win32-x64/AnaliseDesktop.exe` + DLLs.
- `build.ps1` (raiz) orquestra tudo: empacota o Electron (`desktop-gui`),
  empacota `analisar_job.exe` (via PyInstaller, `build/build_python.ps1`),
  baixa/prepara o Tesseract portátil, e monta tudo em
  `dist/AnaliseDesktop/` (uma PASTA — Electron não gera um único `.exe`
  portátil, gera um `.exe` principal + DLLs/recursos ao redor; copiar só o
  `.exe` sem o resto da pasta NÃO funciona).
- Não existe mais `desktop.js` (CLI por terminal) — foi removido e
  substituído por esta GUI Electron, a pedido do usuário ("eu quero uma
  GUI bonitinha, igual essa do print só que para desktop").

### Por que isso importa para uma IA editando o código

- Uma mudança em `analisar_job.py` (ex.: novo campo, nova regra) afeta os
  **dois modos automaticamente**, porque os dois chamam o mesmo script/exe.
  Não precisa duplicar lógica.
- Uma mudança em `controllers/job_pro.controller.js` ou no schema do MySQL
  **só afeta o Modo API** — o Modo Desktop nem importa esses arquivos.
- Uma mudança em `desktop-gui/server/controller.js` ou `jobStore.js` **só
  afeta o Modo Desktop**.
- Uma mudança visual no dashboard pedida de forma genérica ("muda a cor do
  topbar") provavelmente precisa ser replicada em `frontend/index.html`
  (Modo API) **e** `desktop-gui/frontend/index.html` (Modo Desktop) — pare
  e pergunte/confirme qual(is) modo(s) é(são) o alvo antes de editar só um.
- Se pedirem "salvar em outro lugar" ou "mudar o formato de saída", pergunte
  (ou confira pelo contexto) qual dos dois modos é o alvo — API grava no
  MySQL + JSON sidecar, Desktop grava em `data/jobs.json` local.

## Fluxo de dados ponta a ponta (Modo API)

1. Cliente faz `POST /api/jobs/analisar` com `{ pasta_raiz, num_job }`.
2. Controller dá `spawn` no analisador, passando `pasta_raiz` como argumento.
3. `analisar_job.py` varre a pasta, roda cada elemento de `ELEMENTOS` em
   sequência (cada um com seu "tipo" → função em `PROCESSADORES`), monta o
   checklist de alertas, e imprime **um único JSON no stdout** (logs de
   progresso vão para stderr, de propósito, para não poluir o JSON).
4. Controller faz parse do stdout a partir do primeiro `{` (ignora qualquer
   warning de lib Python que vaze antes), salva esse JSON cru em
   `data/jobs/<num_job>_<timestamp>.json` (sidecar, útil para debug/auditoria
   mesmo que o banco falhe) e extrai os campos relevantes pra fazer upsert em
   `jobs_pro` (chave única `num_job`).
5. Frontend consulta `GET /api/jobs` (lista) e `GET /api/jobs/:id` (detalhe,
   inclui `raw_resultado` — o JSON completo salvo como texto).

No Modo Desktop os passos 1–3 são os mesmos (a GUI Electron faz o mesmo
`POST /api/jobs/analisar` contra o próprio servidor Express local, em vez
de um servidor remoto), mas o passo 4 vira "faz upsert em `data/jobs.json`
local, por `num_job`, com `raw_resultado` guardado como objeto (não
string)" — sem MySQL, sem rede.

## Convenções e pontos de atenção

- **Texto sem acentuação nos `.ps1`** é proposital (evita erro de encoding
  no PowerShell de VMs Windows). Não "corrija" para incluir acentos.
- `caminhoAnalisadorPadrao()`/`usaScriptPy()` aparecem duplicados (com a
  mesma lógica) em `controllers/job_pro.controller.js` e em
  `desktop-gui/server/controller.js`, porque cada um resolve o caminho do
  `analisar_job.exe` em relação ao **seu próprio** `baseDir`. Isso é
  intencional — não vale a pena abstrair para um módulo compartilhado sem
  avaliar como fica o empacotamento (um é `pkg`, o outro é
  `electron-packager`, com convenções de pasta diferentes).
- `process.pkg` é a forma de detectar "estou rodando empacotado (`pkg`) ou
  via `node arquivo.js`" — só vale para o Modo API, se algum dia ele for
  empacotado assim. **Não use `process.pkg` dentro de `desktop-gui/`**:
  Electron não usa `pkg`, a checagem correta lá é `app.isPackaged` (ver
  `desktop-gui/main.js`), que já resolve o `baseDir` certo e injeta via
  `createApp({ baseDir, ... })`/`createController({ baseDir, ... })` —
  essas duas funções são fábricas justamente para receber esse `baseDir`
  de fora e ficarem testáveis com Node puro, sem precisar do Electron de
  verdade rodando.
- O schema (`migrations/001_init.sql`) é **MySQL**, não SQLite — usa
  `AUTO_INCREMENT`, `ON UPDATE CURRENT_TIMESTAMP`, `UNIQUE KEY`, etc.
  `db/connection.js` roda esse arquivo inteiro contra o MySQL na
  inicialização (idempotente via `IF NOT EXISTS`), e depois confere/adiciona
  colunas novas que não existiam (`supply`, `finap`) via
  `INFORMATION_SCHEMA.COLUMNS` — é o jeito do projeto evoluir o schema sem
  migrations numeradas de verdade. Se adicionar uma coluna nova, siga esse
  padrão (adicione ao `CREATE TABLE` E à checagem de colunas novas).
- `.env` nunca é commitado (`.gitignore`); `.env.example` é a fonte da
  verdade de quais variáveis existem — mantenha os dois em sincronia.
- Pastas geradas (`dist/`, `data/`, `logs/`, `node_modules/`,
  `build/.venv-build/`, artefatos do PyInstaller) são todas ignoradas —
  não assuma que existem no checkout limpo.

## Onde cada coisa fica

```
server.js                           Modo API — bootstrap do Express
desktop-gui/main.js                 Modo Desktop — processo principal do Electron
desktop-gui/server/app.js           Modo Desktop — fábrica do Express local
desktop-gui/server/controller.js    Modo Desktop — orquestra spawn + jobStore
desktop-gui/server/jobStore.js      Modo Desktop — "banco" local em data/jobs.json
desktop-gui/frontend/index.html     Modo Desktop — UI (cópia do frontend/index.html)
desktop-gui/package.json            Modo Desktop — deps + build:win (electron-packager)
routes/api.routes.js                Modo API — rotas HTTP
controllers/job_pro.controller.js   Modo API — orquestra spawn + MySQL
db/connection.js                    Modo API — pool mysql2/promise
migrations/001_init.sql             Modo API — schema MySQL da tabela jobs_pro
services/analisar_job.py            Os DOIS modos — todo o core de negócio
services/ler_jobs.py                CLI auxiliar p/ inspecionar data/jobs/*.json
frontend/index.html                 Modo API — UI estática servida pelo Express
docker-compose.yml                  Modo API — sobe só o MySQL
ecosystem.config.js                 Modo API — config do PM2
.env.example                        Modo API — variáveis de conexão MySQL + PORT
init_vm.txt                         Modo API — setup inicial da VM
instalar-vm.ps1 / start.ps1         Modo API — firewall, tarefa agendada, start
build.ps1                           Modo Desktop — empacota Electron + analisar_job.exe + Tesseract
build/build_python.ps1              Os DOIS modos — empacota só o analisador Python
requirements.txt                    Os DOIS modos — deps Python do analisador
```

## Perguntas que vale fazer antes de implementar algo

- A mudança é uma **regra de negócio da análise** (o que extrair, de onde,
  quais limiares)? → mexe em `services/analisar_job.py`, afeta os dois modos.
- É sobre **como o resultado é entregue/guardado**? → identifique o modo
  (API → `controller`/MySQL; Desktop → `desktop-gui/server/controller.js`/
  `data/jobs.json`) antes de editar.
- É sobre **infraestrutura/deploy**? → confirme se é VM (Docker+PM2) ou
  pacote desktop (Electron+PyInstaller) — as duas trilhas de build
  (`build.ps1` vs `init_vm.txt`) não se misturam.
- É uma **mudança visual** (cor, layout, texto da tela)? → ela normalmente
  precisa ir em `frontend/index.html` E `desktop-gui/frontend/index.html`
  juntos, pra não deixar os dois modos com dashboards diferentes.
