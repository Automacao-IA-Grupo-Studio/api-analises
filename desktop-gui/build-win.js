// build-win.js - empacota o app Electron para Windows x64 SEM usar
// electron-packager / extract-zip.
//
// Motivo: o extract-zip (usado por electron/install.js e pelo packager)
// trava silenciosamente no Node 26 - extrai 1 arquivo, a promise nunca
// resolve e o processo sai com codigo 0, sem erro nenhum. Aqui o zip do
// Electron e baixado pelo @electron/get (funciona em qualquer Node) e
// extraido pelo tar do Windows (bsdtar, vem no Windows 10+).
//
// Resultado: ../dist/build/AnaliseDesktop-win32-x64/AnaliseDesktop.exe

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const raiz = __dirname;
const saida = path.resolve(raiz, '..', 'dist', 'build', 'AnaliseDesktop-win32-x64');
const versao = require('electron/package.json').version;

function rodar(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: process.platform === 'win32', ...opts });
  if (r.status !== 0) throw new Error(`Falhou (exit ${r.status}): ${cmd} ${args.join(' ')}`);
}

function extrairZip(zip, destino) {
  if (process.platform === 'win32') {
    // Caminho completo: evita pegar um tar de GNU (ex.: do Git) que nao abre .zip
    const tarWin = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe');
    rodar(`"${tarWin}"`, ['-xf', `"${zip}"`, '-C', `"${destino}"`]);
  }
  else rodar('unzip', ['-q', zip, '-d', destino]);
}

async function main() {
  // @electron/get vem como dependencia do pacote "electron" e pode ficar
  // aninhado dentro dele, entao resolvemos a partir da pasta do electron.
  const dirElectron = path.dirname(require.resolve('electron/package.json'));
  const { downloadArtifact } = require(require.resolve('@electron/get', { paths: [dirElectron, raiz] }));
  console.log(`Baixando Electron v${versao} (win32-x64)...`);
  const zip = await downloadArtifact({
    version: versao,
    artifactName: 'electron',
    platform: 'win32',
    arch: 'x64',
    checksums: require('electron/checksums.json'),
  });
  console.log('Zip:', zip);

  fs.rmSync(saida, { recursive: true, force: true });
  fs.mkdirSync(saida, { recursive: true });
  console.log('Extraindo...');
  extrairZip(zip, saida);

  const exeOrig = path.join(saida, 'electron.exe');
  if (!fs.existsSync(exeOrig)) throw new Error('electron.exe nao apareceu apos extrair ' + zip);
  fs.renameSync(exeOrig, path.join(saida, 'AnaliseDesktop.exe'));
  fs.rmSync(path.join(saida, 'resources', 'default_app.asar'), { force: true });

  // Codigo do app em resources/app (o Electron carrega essa pasta no lugar
  // do app padrao). Dependencias: so as de producao.
  const app = path.join(saida, 'resources', 'app');
  fs.mkdirSync(app, { recursive: true });
  for (const item of ['main.js', 'package.json', 'package-lock.json']) {
    fs.copyFileSync(path.join(raiz, item), path.join(app, item));
  }
  fs.cpSync(path.join(raiz, 'server'), path.join(app, 'server'), { recursive: true });
  fs.cpSync(path.join(raiz, 'frontend'), path.join(app, 'frontend'), { recursive: true });
  console.log('Instalando dependencias de producao no app...');
  rodar('npm', ['install', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'], { cwd: app });

  console.log('OK:', path.join(saida, 'AnaliseDesktop.exe'));
}

main().catch(err => { console.error('ERRO:', err.message); process.exit(1); });
