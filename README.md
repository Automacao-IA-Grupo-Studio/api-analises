# API Análises — Studio Fiscal

API que analisa pastas de documentos (contratos, CNPJ, QSA, faturamento etc.)
e expõe os resultados via HTTP + um frontend simples. Node/Express na frente,
um script Python por trás (extração de PDF/XLSX/OCR).

Dois jeitos totalmente diferentes de usar o projeto — veja qual é o seu caso:

| | Modo API (VM) | Modo Desktop (build) |
|---|---|---|
| Para quem | Time todo, multiusuário, histórico centralizado | Uma pessoa, análise avulsa, sem servidor |
| Onde roda | Numa VM, sempre ligada | No PC de qualquer usuário |
| Banco de dados | MySQL (em Docker) | Nenhum |
| Resultado | Fica salvo no banco + JSON em `data/jobs/`, consultado pelo frontend/API | Um `.txt` com o JSON bruto, na pasta onde o app rodou |
| Como sobe | `init_vm.txt` (uma vez) + PM2 | `.\build.ps1` gera um `.exe` portátil |

## Modo 1 — API na VM (produção, multiusuário)

Arquitetura:

```
┌─────────────── VM Windows ───────────────┐
│                                           │
│  PM2 ──► node server.js  (porta 3030)    │
│              │                            │
│              ├─► spawn analisar_job.py/.exe
│              │     (lê \\studiofiscal\...)│
│              │                            │
│              └─► MySQL ◄── Docker Compose │
│                   (127.0.0.1:3306)        │
└───────────────────────────────────────────┘
```

A API roda **fora** do Docker, gerenciada pelo PM2 — só o MySQL fica em
container. Isso é proposital: quando a API também rodava em container, ela
não conseguia acessar os compartilhamentos de rede (`\\studiofiscal\...`)
direito.

**Setup (uma vez, numa VM Windows nova, com Docker Desktop já instalado):**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex (Get-Content .\init_vm.txt -Raw)"
```

Isso instala Node, Python, Tesseract e PM2; sobe o MySQL via
`docker compose up -d`; cria o `.env`; e registra a API para iniciar sozinha
(via PM2) no logon, liberando a porta 3030 no firewall.

**Dia a dia:**

```powershell
.\start.ps1          # garante que MySQL (Docker) + API (PM2) estão no ar
pm2 logs api-analises  # acompanhar logs
pm2 status              # ver se está no ar
pm2 restart ecosystem.config.js   # reiniciar depois de um git pull
```

Acesse `http://localhost:3030` (ou `http://IP-DA-VM:3030` de outra máquina
na rede).

## Modo 2 — App Desktop (uso individual, sem servidor)

Sem API, sem banco de dados. O usuário roda o `.exe`, informa o caminho da
pasta de rede a analisar (ex.: `\\studiofiscal\Temporarios\001`), e o
resultado (**JSON bruto**, igual ao que o analisador devolve) é salvo num
`.txt` na própria pasta onde o app foi executado.

**Gerar o pacote** (numa máquina de build Windows, com Node.js e Python
instalados — a própria VM preparada pelo `init_vm.txt` serve, Docker não é
necessário para isso):

```powershell
.\build.ps1
```

Isso gera `dist\AnaliseDesktop\` com:

- `desktop.exe` — o app desktop empacotado (via `pkg`)
- `analisar_job.exe` — o analisador Python empacotado (via `PyInstaller`)
- `tesseract\` — OCR portátil, sem instalador
- `iniciar.bat` — dê dois cliques, informe a pasta, pronto
- `LEIA-ME.txt` — instruções para quem só vai *usar* o pacote

**Copie a pasta `dist\AnaliseDesktop\` inteira** (ou o
`dist\AnaliseDesktop.zip`) para a máquina de destino. Nada mais precisa
estar instalado lá.

> Detalhe técnico: o `build.ps1` precisa rodar no Windows porque o
> PyInstaller não compila cruzado (um `.exe` Windows só sai rodando em
> Windows). O build do `desktop.exe` (lado Node) já roda tanto em Windows
> quanto em Linux/Mac, já que usa cross-compile do `pkg`.

**Rodar sem empacotar (dev):** `npm run desktop` (ou `node desktop.js`),
com Python e as deps de `requirements.txt` instaladas.

## Estrutura

```
server.js                    servidor Express (Modo API)
desktop.js                   app desktop, sem API/banco (Modo Desktop)
routes/api.routes.js          rotas HTTP
controllers/job_pro.controller.js   lógica das rotas + chama o analisador
db/connection.js              conexão MySQL (mysql2) — usada só no Modo API
migrations/001_init.sql       schema da tabela jobs_pro (MySQL)
services/analisar_job.py      analisador (chamado como subprocess ou .exe) — usado pelos dois modos
services/ler_jobs.py          CLI auxiliar p/ inspecionar os JSONs em data/jobs/
frontend/index.html           UI estática do Modo API
docker-compose.yml            sobe só o MySQL (Modo API)
ecosystem.config.js           config do PM2 (Modo API)
build.ps1                     gera o pacote desktop autocontido (Modo Desktop)
build/build_python.ps1        empacota só o lado Python (usado pelos dois modos)
init_vm.txt                   setup inicial da VM (Modo API)
instalar-vm.ps1 / start.ps1   firewall, tarefa agendada e start do dia a dia (Modo API)
```

## API (Modo 1)

- `GET  /health` — status da API + banco
- `GET  /api/jobs` — lista todos os jobs analisados
- `GET  /api/jobs/:id` — detalhes de um job (inclui resultado bruto)
- `POST /api/jobs/analisar` — dispara uma análise
  — body: `{ "pasta_raiz": "...", "num_job": "..." }`
