// main.js — processo principal do Electron.
// Sobe um servidor Express local (loopback, porta escolhida pelo SO — nunca
// alcançável de fora desta máquina) e abre uma janela nativa carregando o
// mesmo dashboard usado no Modo API, só que lendo/gravando num arquivo JSON
// local em vez de bater numa API remota.
//
// Tela de logs (meio escondida): Ctrl+Shift+L, ou tecla Alt → Ferramentas → Logs.

const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');
const http = require('http');
const logger = require('./server/logger');
const { createApp } = require('./server/app');

let janelaPrincipal = null;
let janelaLogs = null;
let servidorHttp = null;
let portaServidor = null;

// Pasta onde está o executável principal (quando empacotado) — é ao lado dela
// que esperamos analisar_job.exe, tesseract\ e onde fica data\ (jobs.json e
// logs). Em desenvolvimento, usamos a própria pasta do projeto.
function baseDir() {
  return app.isPackaged ? path.dirname(process.execPath) : __dirname;
}

// Logs começam antes de qualquer outra coisa pra pegar até falha de startup.
logger.init(path.join(baseDir(), 'data', 'logs'));
process.on('uncaughtException', err => logger.erro('[main] uncaughtException:', err));
process.on('unhandledRejection', err => logger.erro('[main] unhandledRejection:', err));

function iniciarServidor() {
  return new Promise((resolve, reject) => {
    const expressApp = createApp({
      baseDir: baseDir(),
      pyScriptPath: path.join(__dirname, '..', 'services', 'analisar_job.py'),
      dbFile: path.join(baseDir(), 'data', 'jobs.json'),
      frontendDir: path.join(__dirname, 'frontend'),
    });

    // Porta 0 = o sistema operacional escolhe uma porta livre. Como só este
    // app acessa esse servidor (loopback), não precisa de porta fixa.
    servidorHttp = http.createServer(expressApp);
    servidorHttp.listen(0, '127.0.0.1', () => {
      resolve(servidorHttp.address().port);
    });
    servidorHttp.on('error', reject);
  });
}

// Encaminha problemas da página (console.error, falha de carga, crash) pro log.
function observarJanela(janela, nome) {
  const wc = janela.webContents;
  // Electron <= 34 manda (event, level, message, line, source); 35+ manda um objeto.
  wc.on('console-message', (...a) => {
    const d = a[0] && a[0].message !== undefined ? a[0] : { level: a[1], message: a[2], lineNumber: a[3], sourceId: a[4] };
    const nivel = d.level === 3 || d.level === 'error' ? 'erro' : d.level === 2 || d.level === 'warning' ? 'aviso' : null;
    if (nivel) logger[nivel](`[tela:${nome}] ${d.message} (${d.sourceId || ''}:${d.lineNumber || ''})`);
  });
  wc.on('did-fail-load', (_e, codigo, desc, url) => logger.erro(`[tela:${nome}] falha ao carregar ${url}: ${desc} (${codigo})`));
  wc.on('render-process-gone', (_e, det) => logger.erro(`[tela:${nome}] processo da tela encerrou: ${det.reason}`));
}

function abrirLogs() {
  if (janelaLogs && !janelaLogs.isDestroyed()) {
    if (janelaLogs.isMinimized()) janelaLogs.restore();
    janelaLogs.focus();
    return;
  }
  if (!portaServidor) return;
  janelaLogs = new BrowserWindow({
    width: 1000, height: 640, minWidth: 640, minHeight: 360,
    title: 'Logs — Análise Desktop',
    autoHideMenuBar: true,
    parent: janelaPrincipal || undefined,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  janelaLogs.loadURL(`http://127.0.0.1:${portaServidor}/logs.html`);
  janelaLogs.on('closed', () => { janelaLogs = null; });
}

function montarMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Arquivo', submenu: [{ label: 'Sair', role: 'quit' }] },
    {
      label: 'Ferramentas',
      submenu: [
        { label: 'Ver logs', accelerator: 'CmdOrCtrl+Shift+L', click: abrirLogs },
        {
          label: 'Abrir pasta de logs',
          click: () => { const f = logger.caminhoArquivo(); if (f) shell.showItemInFolder(f); },
        },
        { type: 'separator' },
        { label: 'Recarregar tela', accelerator: 'CmdOrCtrl+R', click: () => janelaPrincipal?.reload() },
      ],
    },
  ]));
}

async function criarJanela() {
  logger.info(`Iniciando — empacotado=${app.isPackaged} | baseDir=${baseDir()} | exec=${process.execPath} | ` +
              `${process.platform}/${process.arch} | electron=${process.versions.electron} | node=${process.versions.node}`);
  try {
    portaServidor = await iniciarServidor();
    logger.info(`Servidor local em http://127.0.0.1:${portaServidor}`);
  } catch (err) {
    logger.erro('[FATAL] Não foi possível iniciar o servidor local:', err);
    app.quit();
    return;
  }

  montarMenu();

  janelaPrincipal = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: 'Análise Desktop — Studio Fiscal',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  observarJanela(janelaPrincipal, 'principal');

  // Garante o atalho mesmo se o menu estiver escondido.
  janelaPrincipal.webContents.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && input.control && input.shift && input.key.toLowerCase() === 'l') {
      event.preventDefault();
      abrirLogs();
    }
  });

  janelaPrincipal.loadURL(`http://127.0.0.1:${portaServidor}`);

  janelaPrincipal.on('closed', () => {
    janelaPrincipal = null;
  });
}

app.whenReady().then(criarJanela);

app.on('window-all-closed', () => {
  if (servidorHttp) servidorHttp.close();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) criarJanela();
});
