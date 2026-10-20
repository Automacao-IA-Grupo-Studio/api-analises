const { spawn }  = require('child_process');
const path        = require('path');
const fs          = require('fs');
const { getPool } = require('../db/connection');

const DATA_DIR     = path.join(__dirname, '../data/jobs');
const PYTHON_BIN   = process.env.PYTHON_BIN || 'python3';
const SCRIPT_PATH  = path.join(__dirname, '../services/analisar_job.py');

// ─────────────────────────────────────────────────────────────────────────────
//  GET /api/jobs  — lista todos os jobs
// ─────────────────────────────────────────────────────────────────────────────
exports.listarJobs = async (req, res) => {
  try {
    const pool = getPool();
    const [rows] = await pool.query(`
      SELECT
        id, num_job, pasta_raiz, status_analise,
        contrato_existe, procuracao_existe, honorarios, gross_up, passivo,
        data_abertura, simples_nacional, socios,
        situacao_fiscal, regularize, perfil,
        faturamento, fastpass,
        alerta_sem_contrato, alerta_sem_procuracao, alerta_baixo_fat, alerta_regularize,
        analisado_em, created_at
      FROM jobs_pro
      ORDER BY analisado_em DESC
    `);
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
    const pool = getPool();
    const [rows] = await pool.query(
      'SELECT * FROM jobs_pro WHERE id = ?',
      [req.params.id]
    );
    if (!rows.length) {
      return res.status(404).json({ error: 'Job não encontrado' });
    }
    res.json(rows[0]);
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

  // Executa o script Python como subprocess
  const python = spawn(PYTHON_BIN, [SCRIPT_PATH, pasta_raiz], {
    env: { ...process.env, PYTHONUTF8: '1' },
  });

  let stdout = '';
  let stderr = '';

  python.stdout.on('data', chunk => { stdout += chunk.toString('utf8'); });
  python.stderr.on('data', chunk => {
    const line = chunk.toString('utf8');
    stderr += line;
    process.stdout.write(`[py] ${line}`);  // repassa logs do Python
  });

  python.on('error', err => {
    console.error('[spawn] Erro ao iniciar Python:', err.message);
    return res.status(500).json({
      error: 'Não foi possível iniciar o interpretador Python',
      detalhes: err.message,
    });
  });

  python.on('close', async code => {
    if (code !== 0) {
      console.error(`[analisar] Python saiu com código ${code}`);
      return res.status(500).json({
        error: `Análise falhou (exit ${code})`,
        detalhes: stderr.slice(-1000),
      });
    }

    // Parse do JSON retornado pelo script
    let analise;
    try {
      analise = JSON.parse(stdout);
    } catch (e) {
      console.error('[analisar] JSON inválido:', stdout.slice(0, 300));
      return res.status(500).json({
        error: 'Resposta do analisador não é JSON válido',
        raw: stdout.slice(0, 300),
      });
    }

    if (analise.erro) {
      return res.status(422).json({ error: analise.erro });
    }

    // ── Salva JSON sidecar em data/jobs/ ───────────────────────────────────
    try {
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

    // ── Insere (ou atualiza) no MySQL ──────────────────────────────────────
    try {
      const pool = getPool();
      const [result] = await pool.query(`
        INSERT INTO jobs_pro (
          num_job, pasta_raiz,
          contrato_existe, procuracao_existe, honorarios, gross_up, passivo,
          data_abertura, simples_nacional, socios,
          situacao_fiscal, regularize, perfil,
          faturamento, fastpass,
          alerta_sem_contrato, alerta_sem_procuracao, alerta_baixo_fat, alerta_regularize,
          raw_resultado, status_analise, analisado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', NOW())
        ON DUPLICATE KEY UPDATE
          pasta_raiz        = VALUES(pasta_raiz),
          contrato_existe   = VALUES(contrato_existe),
          procuracao_existe = VALUES(procuracao_existe),
          honorarios        = VALUES(honorarios),
          gross_up          = VALUES(gross_up),
          passivo           = VALUES(passivo),
          data_abertura     = VALUES(data_abertura),
          simples_nacional  = VALUES(simples_nacional),
          socios            = VALUES(socios),
          situacao_fiscal   = VALUES(situacao_fiscal),
          regularize        = VALUES(regularize),
          perfil            = VALUES(perfil),
          faturamento       = VALUES(faturamento),
          fastpass          = VALUES(fastpass),
          alerta_sem_contrato   = VALUES(alerta_sem_contrato),
          alerta_sem_procuracao = VALUES(alerta_sem_procuracao),
          alerta_baixo_fat      = VALUES(alerta_baixo_fat),
          alerta_regularize     = VALUES(alerta_regularize),
          raw_resultado     = VALUES(raw_resultado),
          status_analise    = 'ok',
          analisado_em      = NOW()
      `, [
        num_job, pasta_raiz,
        campo('contrato_existe'),   campo('procuracao_existe'),
        campo('honorarios'),        campo('gross_up'),
        campo('passivo'),           campo('data_abertura'),
        campo('simples_nacional'),  campo('socios'),
        campo('situacao_fiscal'),   campo('regularize'),
        campo('perfil'),            campo('faturamento'),
        campo('fastpass'),
        alertaAtivo('SEM CONTRATO'),
        alertaAtivo('SEM PROCURAÇÃO'),
        alertaAtivo('FATURAMENTO MÉDIO ABAIXO DE R$ 20M'),
        alertaAtivo('COM REGULARIZE'),
        JSON.stringify(analise),
      ]);

      const id = result.insertId || null;
      const [rows] = await pool.query('SELECT * FROM jobs_pro WHERE id = ?', [id]);
      console.log(`[analisar] Salvo no banco — id: ${id}`);

      res.status(201).json({
        mensagem: 'Análise concluída e salva com sucesso',
        job: rows[0] || { id, num_job, pasta_raiz },
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
