// logger.js — log do app desktop: buffer em memória (alimenta a tela de logs)
// + arquivo em <pasta do app>\data\logs\app.log.
//
// ⚠ Só escreve na pasta do próprio app (data\logs). NUNCA toca nas pastas de
//   rede analisadas (somente leitura).
//
// Singleton: main.js, app.js e controller.js usam a mesma instância. Se init()
// não for chamado (ex.: teste headless), funciona só em memória.

const fs = require('fs');
const path = require('path');

const MAX_LINHAS = 20000;         // buffer em memória (~130 linhas por job analisado)
const MAX_ARQUIVO = 2 * 1024 * 1024; // 2 MB → rotaciona para app.log.1

let linhas = [];
let proximoId = 1;
let arquivo = null;

function init(dirLogs) {
  try {
    fs.mkdirSync(dirLogs, { recursive: true });
    arquivo = path.join(dirLogs, 'app.log');
    rotacionarSeGrande();
  } catch (err) {
    arquivo = null; // sem disco: segue só em memória
    console.error('[logger] sem arquivo de log:', err.message);
  }
}

function rotacionarSeGrande() {
  try {
    if (arquivo && fs.existsSync(arquivo) && fs.statSync(arquivo).size > MAX_ARQUIVO) {
      fs.renameSync(arquivo, arquivo + '.1'); // sobrescreve o .1 anterior
    }
  } catch { /* ignora */ }
}

function texto(partes) {
  return partes.map(p => {
    if (p instanceof Error) return p.stack || p.message;
    if (typeof p === 'string') return p;
    try { return JSON.stringify(p); } catch { return String(p); }
  }).join(' ');
}

function registrar(nivel, partes) {
  const entrada = { id: proximoId++, ts: new Date().toISOString(), nivel, msg: texto(partes) };
  linhas.push(entrada);
  if (linhas.length > MAX_LINHAS) linhas = linhas.slice(-MAX_LINHAS);

  const linhaArq = `${entrada.ts} [${nivel}] ${entrada.msg.replace(/\r?\n/g, '\n    ')}\n`;
  (nivel === 'ERRO' ? console.error : console.log)(linhaArq.trimEnd());
  if (arquivo) {
    try { fs.appendFileSync(arquivo, linhaArq, 'utf8'); } catch { /* ignora */ }
  }
  return entrada;
}

/** Duração legível: "12,3 s" | "20 min 03 s" | "1 h 02 min". */
function formatarDuracao(ms) {
  const s = Math.max(0, ms) / 1000;
  if (s < 60) return `${s.toFixed(1).replace('.', ',')} s`;
  const total = Math.round(s);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const seg = total % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, '0')} min`;
  return `${m} min ${String(seg).padStart(2, '0')} s`;
}

module.exports = {
  formatarDuracao,
  init,
  info:  (...p) => registrar('INFO', p),
  aviso: (...p) => registrar('AVISO', p),
  erro:  (...p) => registrar('ERRO', p),
  /** Linhas com id > desde (0 = todas). */
  listar(desde = 0) {
    const novas = linhas.filter(l => l.id > desde);
    return { ultimo_id: linhas.length ? linhas[linhas.length - 1].id : desde, linhas: novas };
  },
  /** Limpa só a tela (memória); o arquivo em disco é mantido. */
  limparTela() { linhas = []; },
  caminhoArquivo: () => arquivo,
};
