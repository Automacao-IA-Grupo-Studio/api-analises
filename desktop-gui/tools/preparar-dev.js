// tools/preparar-dev.js — garante que node_modules/electron/dist existe para
// "npm start" (o instalador padrao do electron falha em silencio no Node 26).
// Idempotente: se o Electron ja esta la, nao faz nada.

const fs = require('fs');
const path = require('path');
const { dirElectron, versaoElectron, baixarZip, extrairZip } = require('./electron-zip');

const EXE = { win32: 'electron.exe', darwin: 'Electron.app/Contents/MacOS/Electron', linux: 'electron' };

async function main() {
  const plataforma = process.platform;
  const exeRel = EXE[plataforma];
  if (!exeRel) throw new Error('Plataforma sem suporte: ' + plataforma);

  const base = dirElectron();
  const dist = path.join(base, 'dist');
  const pathTxt = path.join(base, 'path.txt');
  const versaoOk = () => { try { return fs.readFileSync(path.join(dist, 'version'), 'utf8').replace(/^v/, '').trim() === versaoElectron(); } catch { return false; } };

  if (fs.existsSync(path.join(dist, exeRel)) && fs.existsSync(pathTxt) && versaoOk()) return;

  console.log(`Preparando Electron v${versaoElectron()} (${plataforma}/${process.arch}) - so na primeira vez...`);
  const zip = await baixarZip(plataforma, process.arch);
  fs.rmSync(dist, { recursive: true, force: true });
  extrairZip(zip, dist);
  if (!fs.existsSync(path.join(dist, exeRel))) throw new Error(`${exeRel} nao apareceu apos extrair ${zip}`);
  fs.writeFileSync(pathTxt, exeRel);
  console.log('Electron pronto.');
}

main().catch(err => { console.error('ERRO ao preparar o Electron:', err.message); process.exit(1); });
