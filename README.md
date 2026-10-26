# API Análises — Studio Fiscal

API que analisa pastas de documentos (contratos, CNPJ, QSA, faturamento etc.) e
expõe os resultados via HTTP + um frontend simples. Node/Express na frente,
um script Python por trás (extração de PDF/XLSX/OCR), banco **SQLite local**
(sem servidor externo).

## Modo 1 — Executável autocontido (recomendado)

Gera uma pasta portátil que roda em **qualquer Windows, sem instalar nada**
(sem Node, sem Python, sem Tesseract, sem banco de dados externo).

**Numa máquina de build** (Windows, com Node.js e Python já instalados —
a própria VM preparada pelo `init_vm.txt` serve):

```powershell
.\build.ps1
```

Isso gera `dist\ApiAnalises\` com:

- `server.exe` — Node + Express + SQLite empacotados (via `pkg`)
- `analisar_job.exe` — o analisador Python empacotado (via `PyInstaller`)
- `tesseract\` — OCR portátil, sem instalador
- `iniciar.bat` — dê dois cliques e a API sobe em `http://localhost:3030`
- `LEIA-ME.txt` — instruções para quem só vai *usar* o pacote

**Copie a pasta `dist\ApiAnalises\` inteira** (ou o `dist\ApiAnalises.zip`)
para a máquina de destino. Nada mais precisa estar instalado lá.

O banco fica em `data\database.sqlite` dentro da própria pasta — faça backup
dela periodicamente.

> Detalhe técnico: o `build.ps1` precisa rodar no Windows porque o
> PyInstaller não compila cruzado (um `.exe` Windows só sai rodando em
> Windows). O build do `server.exe` (lado Node) já roda tanto em Windows
> quanto em Linux/Mac, já que usa cross-compile do `pkg`.

## Modo 2 — Rodando a partir do código-fonte (desenvolvimento)

Ainda funciona, do jeito de sempre:

```powershell
# Uma vez, numa VM Windows nova:
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex (Get-Content .\init_vm.txt -Raw)"

# No dia a dia:
.\start.ps1 -SemDocker
```

Ou manualmente: `npm install`, `pip install -r requirements.txt`, Tesseract
instalado no PATH, e `node server.js`.

## Estrutura

```
server.js                   servidor Express
routes/api.routes.js         rotas HTTP
controllers/job_pro.controller.js   lógica das rotas + chama o analisador
db/connection.js             conexão SQLite (data/database.sqlite)
migrations/001_init.sql      schema da tabela jobs_pro
services/analisar_job.py     analisador (chamado como subprocess ou .exe)
frontend/index.html          UI estática
build.ps1                    gera o pacote autocontido (Modo 1)
build/build_python.ps1       empacota só o lado Python
```

## API

- `GET  /health` — status da API + banco
- `GET  /api/jobs` — lista todos os jobs analisados
- `GET  /api/jobs/:id` — detalhes de um job (inclui resultado bruto)
- `POST /api/jobs/analisar` — dispara uma análise
  — body: `{ "pasta_raiz": "...", "num_job": "..." }`
