#!/usr/bin/env node
/**
 * desktop.js — App desktop (modo "build") da API Análises
 * ═════════════════════════════════════════════════════════════════════════
 * Sem API HTTP, sem banco de dados. Roda localmente na máquina do usuário:
 *   1. Pergunta o caminho da pasta a analisar (ex.: \\studiofiscal\Temporarios\001)
 *   2. Chama o mesmo analisador Python usado pela API (services/analisar_job.py
 *      em dev, ou analisar_job.exe empacotado ao lado deste executável)
 *   3. Salva o JSON bruto retornado num .txt na pasta onde este app foi
 *      executado (process.cwd())
 *
 * Pensado para gerar um .exe autocontido via `npm run build:desktop`
 * (empacotado com pkg — ver build.ps1).
 */

const { spawn }   = require('child_process');
const readline    = require('readline');
const path         = require('path');
const fs           = require('fs');

// Pasta onde o .exe (ou "node desktop.js") está — é ao lado dela que
// procuramos o analisar_job.exe empacotado.
function baseDir() {
  return process.pkg ? path.dirname(process.execPath) : __dirname;
}

function caminhoAnalisadorPadrao() {
  const exeEmpacotado = path.join(baseDir(), 'analisar_job.exe');
  if (fs.existsSync(exeEmpacotado)) return exeEmpacotado;
  return process.platform === 'win32' ? 'python' : 'python3';
}

function usaScriptPy() {
  const exeEmpacotado = path.join(baseDir(), 'analisar_job.exe');
  return !fs.existsSync(exeEmpacotado);
}

const PYTHON_BIN         = process.env.PYTHON_BIN || caminhoAnalisadorPadrao();
const SCRIPT_ARGS_PREFIX = usaScriptPy() ? [path.join(__dirname, 'services', 'analisar_job.py')] : [];

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const pergunta = texto => new Promise(resolve => rl.question(texto, resolve));

// Roda o analisador numa pasta e devolve o JSON (bruto) que ele imprime no stdout.
function analisar(pastaRaiz) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, [...SCRIPT_ARGS_PREFIX, pastaRaiz], {
      env: { ...process.env, PYTHONUTF8: '1' },
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', chunk => { stdout += chunk.toString('utf8'); });
    proc.stderr.on('data', chunk => {
      const linha = chunk.toString('utf8');
      stderr += linha;
      process.stdout.write(linha); // mostra o progresso do analisador em tempo real
    });

    proc.on('error', err => {
      reject(new Error(`Não foi possível iniciar o analisador (${PYTHON_BIN}): ${err.message}`));
    });

    proc.on('close', code => {
      const jsonStart = stdout.indexOf('{');
      if (jsonStart === -1) {
        return reject(new Error(
          `Analisador não devolveu JSON (código de saída ${code}).\n${stderr.slice(-1000) || stdout.slice(-1000)}`
        ));
      }
      try {
        const analise = JSON.parse(stdout.slice(jsonStart));
        resolve(analise);
      } catch (e) {
        reject(new Error(`Resposta do analisador não é JSON válido: ${e.message}`));
      }
    });
  });
}

function nomeArquivoSaida(numJob) {
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const base = numJob ? numJob.replace(/[^\w\-]/g, '_') : 'analise';
  return `${base}_${ts}.txt`;
}

async function rodarUmaAnalise() {
  const pastaRaiz = (await pergunta('\nCaminho da pasta a analisar (ex.: \\\\studiofiscal\\Temporarios\\001): ')).trim();
  if (!pastaRaiz) {
    console.log('Caminho vazio — nada a fazer.');
    return;
  }
  const numJob = (await pergunta('Número do job (opcional, só pro nome do arquivo — Enter para pular): ')).trim();

  console.log(`\nAnalisando: ${pastaRaiz}\n${'─'.repeat(60)}`);

  let analise;
  try {
    analise = await analisar(pastaRaiz);
  } catch (err) {
    console.error(`\n[ERRO] ${err.message}`);
    return;
  }

  const destino = path.join(process.cwd(), nomeArquivoSaida(numJob));
  fs.writeFileSync(destino, JSON.stringify(analise, null, 2), 'utf8');

  console.log(`${'─'.repeat(60)}`);
  if (analise.erro) {
    console.log(`Análise concluída com erro: ${analise.erro}`);
  } else {
    const r = analise.resumo || {};
    console.log(`Análise concluída: ${r.encontrados ?? '?'}/${r.total ?? '?'} campos encontrados, ${r.alertas_checklist ?? '?'} alerta(s).`);
  }
  console.log(`Resultado salvo em: ${destino}`);
}

async function main() {
  console.log('=== API Análises — Studio Fiscal (app desktop) ===');
  console.log('Resultado de cada análise é salvo em JSON bruto, num .txt, nesta pasta.\n');

  let continuar = true;
  while (continuar) {
    await rodarUmaAnalise();
    const resp = (await pergunta('\nAnalisar outra pasta? (S/n): ')).trim().toLowerCase();
    continuar = resp === '' || resp === 's' || resp === 'sim';
  }

  console.log('\nAté mais!');
  rl.close();
}

main().catch(err => {
  console.error('[FATAL]', err);
  process.exitCode = 1;
  rl.close();
});
