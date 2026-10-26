const { spawn }  = require('child_process');
const path        = require('path');
const fs          = require('fs');
const { getDB }   = require('../db/connection');

const DATA_DIR    = path.join(baseDir(), 'data', 'jobs');
const PYTHON_BIN   = process.env.PYTHON_BIN || caminhoAnalisadorPadrao();
const SCRIPT_ARGS_PREFIX = usaScriptPy() ? [path.join(__dirname, '../services/analisar_job.py')] : [];

// Quando empacotado (process.pkg definido), o caminho base é a pasta onde
// está o .exe; em desenvolvimento, é a raiz do projeto.
function baseDir() {
  return process.pkg ? path.dirname(process.execPath) : path.join(__dirname, '..');
}

// Se existir um analisar_job.exe standalone (gerado com PyInstaller) ao lado
// do executável/projeto, usa ele — não precisa de Python instalado na máquina.
// Caso contrário, cai para "python3 services/analisar_job.py" (modo dev).
function caminhoAnalisadorPadrao() {
  const exeEmpacotado = path.join(baseDir(), 'analisar_job.exe');
  if (fs.existsSync(exeEmpacotado)) return exeEmpacotado;
  return process.platform === 'win32' ? 'python' : 'python3';
}

function usaScriptPy() {
  const exeEmpacotado = path.join(baseDir(), 'analisar_job.exe');
  return !fs.existsSync(exeEmpacotado);
}

// ─────────────────────────────────────────────────────────────────────────────
//  GET /api/jobs  — lista todos os jobs
// ─────────────────────────────────────────────────────────────────────────────
exports.listarJobs = async (req, res) => {
  try {
    const db = getDB();
    const rows = db.prepare(`
      SELECT
        id, num_job, pasta_raiz, status_analise,
        contrato_existe, procuracao_existe, honorarios, gross_up, passivo,
        data_abertura, simples_nacional, socios,
        situacao_fiscal, regularize, perfil,
        faturamento, fastpass, supply, finap,
        alerta_sem_contrato, alerta_sem_procuracao, alerta_baixo_fat, alerta_regularize,
        analisado_em, created_at
      FROM jobs_pro
      ORDER BY analisado_em DESC
    `).all();
    res.json({ total: rows.length, jobs: rows });
  } catch (err) {
    console.error('[listarJobs]', err);
    res.status(500).json({ error: err.message });
  }
};

// ─────────────────────────────────────────────────────────────────────────────
//  GET /api/jobs/:id  — detalhes de um job (inclui raw_resultado)
// ─────────────────────────────────────────────────────────────────────────────
exports.obterJob = async (req, res) => {
  try {
    const db  = getDB();
    const row = db.prepare('SELECT * FROM jobs_pro WHERE id = ?').get(req.params.id);
    if (!row) {
      return res.status(404).json({ error: 'Job não encontrado' });
    }
    res.json(row);
  } catch (err) {
    console.error('[obterJob]', err);
    res.status(500).json({ error: err.message });
  }
};

// ─────────────────────────────────────────────────────────────────────────────
//  POST /api/jobs/analisar  — dispara análise de um diretório
//  Body: { pasta_raiz: "...", num_job: "..." }
// ─────────────────────────────────────────────────────────────────────────────
exports.analisarJob = async (req, res) => {
  const { pasta_raiz, num_job } = req.body || {};

  if (!pasta_raiz || !num_job) {
    return res.status(400).json({
      error: 'Campos obrigatórios: pasta_raiz, num_job',
    });
  }

  console.log(`\n[analisar] Iniciando: ${num_job} — ${pasta_raiz}`);

  // Executa o analisador (exe standalone em produção, ou "python3 script.py" em dev)
  const python = spawn(PYTHON_BIN, [...SCRIPT_ARGS_PREFIX, pasta_raiz], {
    env: { ...process.env, PYTHONUTF8: '1' },
    windowsHide: true, // evita janela de console piscando ao chamar o analisar_job.exe
  });

  let stdout = '';
  let stderr = '';

  python.stdout.on('data', chunk => { stdout += chunk.toString('utf8'); });
  python.stderr.on('data', chunk => {
    const line = chunk.toString('utf8');
    stderr += line;
    process.stdout.write(`[analisador] ${line}`);  // repassa logs do analisador
  });

  python.on('error', err => {
    console.error('[spawn] Erro ao iniciar analisador:', err.message);
    return res.status(500).json({
      error: 'Não foi possível iniciar o analisador de documentos',
      detalhes: err.message,
    });
  });

  python.on('close', async code => {
    // Parse do JSON retornado pelo script
    // Ignora qualquer linha de warning antes do JSON (ex: warnings do pymupdf)
    let analise;
    try {
      const jsonStart = stdout.indexOf('{');
      if (jsonStart === -1) throw new Error('Nenhum JSON encontrado no stdout');
      const jsonStr = stdout.slice(jsonStart);
      analise = JSON.parse(jsonStr);
    } catch (e) {
      // Não veio JSON válido: aí sim é uma falha "crua" (crash, script não encontrado etc.)
      if (code !== 0) {
        console.error(`[analisar] Analisador saiu com código ${code}`);
        return res.status(500).json({
          error: `Análise falhou (exit ${code})`,
          detalhes: stderr.slice(-1000) || stdout.slice(-1000),
        });
      }
      console.error('[analisar] JSON inválido:', stdout.slice(0, 500));
      return res.status(500).json({
        error: 'Resposta do analisador não é JSON válido',
        raw: stdout.slice(0, 500),
      });
    }

    // O script pode sair com código != 0 e ainda assim ter devolvido um JSON
    // de erro amigável (ex.: "Diretório não encontrado"). Nesse caso usamos
    // a mensagem dele em vez de um erro genérico.
    if (analise.erro) {
      return res.status(422).json({ error: analise.erro });
    }
    if (code !== 0) {
      console.error(`[analisar] Analisador saiu com código ${code}`);
      return res.status(500).json({
        error: `Análise falhou (exit ${code})`,
        detalhes: stderr.slice(-1000),
      });
    }

    // ── Salva JSON sidecar em data/jobs/ ───────────────────────────────────
    try {
      fs.mkdirSync(DATA_DIR, { recursive: true });
      const ts       = new Date().toISOString().replace(/[:.]/g, '-');
      const fname    = `${num_job.replace(/[^\w\-]/g, '_')}_${ts}.json`;
      const filepath = path.join(DATA_DIR, fname);
      fs.writeFileSync(filepath, JSON.stringify(analise, null, 2), 'utf8');
      console.log(`[analisar] Sidecar salvo: ${filepath}`);
    } catch (e) {
      console.warn('[analisar] Não foi possível salvar sidecar:', e.message);
    }

    // ── Extrai campos do resultado ─────────────────────────────────────────
    const resultados = analise.resultados || [];
    const checklist  = analise.checklist  || [];

    const campo = id => {
      const r = resultados.find(x => x.id === id);
      return r?.valor || null;
    };

    const alertaAtivo = desc => {
      const c = checklist.find(x => x.descricao === desc);
      return c?.alerta ? 1 : 0;
    };

    // ── Insere (ou atualiza) no SQLite ──────────────────────────────────────
    try {
      const db = getDB();
      const stmt = db.prepare(`
        INSERT INTO jobs_pro (
          num_job, pasta_raiz,
          contrato_existe, procuracao_existe, honorarios, gross_up, passivo,
          data_abertura, simples_nacional, socios,
          situacao_fiscal, regularize, perfil,
          faturamento, fastpass, supply, finap,
          alerta_sem_contrato, alerta_sem_procuracao, alerta_baixo_fat, alerta_regularize,
          raw_resultado, status_analise, analisado_em
        ) VALUES (
          @num_job, @pasta_raiz,
          @contrato_existe, @procuracao_existe, @honorarios, @gross_up, @passivo,
          @data_abertura, @simples_nacional, @socios,
          @situacao_fiscal, @regularize, @perfil,
          @faturamento, @fastpass, @supply, @finap,
          @alerta_sem_contrato, @alerta_sem_procuracao, @alerta_baixo_fat, @alerta_regularize,
          @raw_resultado, 'ok', strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
        )
        ON CONFLICT(num_job) DO UPDATE SET
          pasta_raiz        = excluded.pasta_raiz,
          contrato_existe    = excluded.contrato_existe,
          procuracao_existe  = excluded.procuracao_existe,
          honorarios         = excluded.honorarios,
          gross_up           = excluded.gross_up,
          passivo            = excluded.passivo,
          data_abertura      = excluded.data_abertura,
          simples_nacional   = excluded.simples_nacional,
          socios             = excluded.socios,
          situacao_fiscal    = excluded.situacao_fiscal,
          regularize         = excluded.regularize,
          perfil             = excluded.perfil,
          faturamento        = excluded.faturamento,
          fastpass           = excluded.fastpass,
          supply             = excluded.supply,
          finap              = excluded.finap,
          alerta_sem_contrato   = excluded.alerta_sem_contrato,
          alerta_sem_procuracao = excluded.alerta_sem_procuracao,
          alerta_baixo_fat      = excluded.alerta_baixo_fat,
          alerta_regularize     = excluded.alerta_regularize,
          raw_resultado      = excluded.raw_resultado,
          status_analise     = 'ok',
          analisado_em       = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
      `);

      stmt.run({
        num_job, pasta_raiz,
        contrato_existe:   campo('contrato_existe'),
        procuracao_existe: campo('procuracao_existe'),
        honorarios:        campo('honorarios'),
        gross_up:          campo('gross_up'),
        passivo:           campo('passivo'),
        data_abertura:     campo('data_abertura'),
        simples_nacional:  campo('simples_nacional'),
        socios:            campo('socios'),
        situacao_fiscal:   campo('situacao_fiscal'),
        regularize:        campo('regularize'),
        perfil:            campo('perfil'),
        faturamento:       campo('faturamento'),
        fastpass:          campo('fastpass'),
        supply:            campo('supply'),
        finap:             campo('finap'),
        alerta_sem_contrato:   alertaAtivo('SEM CONTRATO'),
        alerta_sem_procuracao: alertaAtivo('SEM PROCURAÇÃO'),
        alerta_baixo_fat:      alertaAtivo('FATURAMENTO MÉDIO ABAIXO DE R$ 20M'),
        alerta_regularize:     alertaAtivo('COM REGULARIZE'),
        raw_resultado: JSON.stringify(analise),
      });

      const row = db.prepare('SELECT * FROM jobs_pro WHERE num_job = ?').get(num_job);
      console.log(`[analisar] Salvo no banco — id: ${row?.id}`);

      res.status(201).json({
        mensagem: 'Análise concluída e salva com sucesso',
        job: row || { num_job, pasta_raiz },
      });
    } catch (dbErr) {
      console.error('[analisar] Erro ao salvar no banco:', dbErr.message);
      // Retorna o resultado da análise mesmo sem banco
      res.status(207).json({
        mensagem: 'Análise concluída, mas não foi possível salvar no banco',
        erro_banco: dbErr.message,
        analise,
      });
    }
  });
};
