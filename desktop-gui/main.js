// main.js — processo principal do Electron.
// Sobe um servidor Express local (loopback, porta escolhida pelo SO — nunca
// alcançável de fora desta máquina) e abre uma janela nativa carregando o
// mesmo dashboard usado no Modo API, só que lendo/gravando num arquivo JSON
// local em vez de bater numa API remota.

const { app, BrowserWindow } = require('electron');
const path = require('path');
const http = require('http');
const { createApp } = require('./server/app');

let janelaPrincipal = null;
let servidorHttp = null;

// Pasta onde está o executável principal (quando empacotado pelo
// electron-packager) — é ao lado dela que esperamos analisar_job.exe e
// tesseract\. Em desenvolvimento, usamos a própria pasta do projeto.
function baseDir() {
  return app.isPackaged ? path.dirname(process.execPath) : __dirname;
}

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

async function criarJanela() {
  let porta;
  try {
    porta = await iniciarServidor();
  } catch (err) {
    console.error('[FATAL] Não foi possível iniciar o servidor local:', err);
    app.quit();
    return;
  }

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

  janelaPrincipal.loadURL(`http://127.0.0.1:${porta}`);

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
