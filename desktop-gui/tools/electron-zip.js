// tools/electron-zip.js — baixa e extrai o zip do Electron SEM extract-zip.
//
// O extract-zip (usado pelo postinstall do "electron" e pelo electron-packager)
// trava em silencio no Node 26: extrai 1 arquivo, a promise nunca resolve e o
// processo sai com exit 0. Aqui o download e feito pelo @electron/get e a
// extracao pelo tar do Windows (bsdtar) / unzip.

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const raiz = path.resolve(__dirname, '..');

function rodar(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: process.platform === 'win32', ...opts });
  if (r.status !== 0) throw new Error(`Falhou (exit ${r.status}): ${cmd} ${args.join(' ')}`);
}

function dirElectron() {
  return path.dirname(require.resolve('electron/package.json', { paths: [raiz] }));
}

function versaoElectron() {
  return require(path.join(dirElectron(), 'package.json')).version;
}

async function baixarZip(platform, arch) {
  // @electron/get vem como dependencia do "electron" e pode ficar aninhado.
  const { downloadArtifact } = require(require.resolve('@electron/get', { paths: [dirElectron(), raiz] }));
  return downloadArtifact({
    version: versaoElectron(),
    artifactName: 'electron',
    platform,
    arch,
    checksums: require(path.join(dirElectron(), 'checksums.json')),
  });
}

function extrairZip(zip, destino) {
  fs.mkdirSync(destino, { recursive: true });
  if (process.platform === 'win32') {
    // Caminho completo: evita pegar um tar GNU (ex.: do Git) que nao abre .zip
    const tarWin = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe');
    rodar(`"${tarWin}"`, ['-xf', `"${zip}"`, '-C', `"${destino}"`]);
  } else {
    rodar('unzip', ['-q', zip, '-d', destino]);
  }
}

module.exports = { raiz, dirElectron, versaoElectron, baixarZip, extrairZip };
