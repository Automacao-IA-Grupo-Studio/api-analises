// controller.js — mesma lógica de controllers/job_pro.controller.js (Modo API),
// adaptada para o jobStore (JSON local) em vez de MySQL.
//
// Exporta uma factory (createController) em vez de funções fixas, pra poder
// injetar onde fica o analisar_job.exe/services/analisar_job.py — isso deixa
// o módulo testável com Node puro (sem precisar do Electron de verdade rodando)
// e também correto quando empacotado pelo electron-packager.

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const jobStore = require('./jobStore');

/**
 * @param {object} opts
 * @param {string} opts.baseDir       Pasta onde procurar analisar_job.exe
 *                                    (pasta do .exe principal quando empacotado;
 *                                    pasta do projeto em desenvolvimento).
 * @param {string} opts.pyScriptPath  Caminho absoluto p/ services/analisar_job.py
 *                                    (fallback quando não há .exe empacotado).
 */
function createController({ baseDir, pyScriptPath }) {
  function caminhoAnalisadorPadrao() {
    const exeEmpacotado = path.join(baseDir, 'analisar_job.exe');
    if (fs.existsSync(exeEmpacotado)) return exeEmpacotado;
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  function usaScriptPy() {
    return !fs.existsSync(path.join(baseDir, 'analisar_job.exe'));
  }

  const PYTHON_BIN = process.env.PYTHON_BIN || caminhoAnalisadorPadrao();
  const SCRIPT_ARGS_PREFIX = usaScriptPy() ? [pyScriptPath] : [];

  // ───────────────────────────────────────────────────────────────────────
  //  GET /api/jobs
  // ───────────────────────────────────────────────────────────────────────
  async function listarJobs(req, res) {
    try {
      const jobs = jobStore.listar();
      res.json({ total: jobs.length, jobs });
    } catch (err) {
      console.error('[listarJobs]', err);
      res.status(500).json({ error: err.message });
    }
  }

  // ───────────────────────────────────────────────────────────────────────
  //  GET /api/jobs/:id  (raw_resultado já vem como objeto, não string)
  // ───────────────────────────────────────────────────────────────────────
  async function obterJob(req, res) {
    try {
      const job = jobStore.obterPorId(req.params.id);
      if (!job) return res.status(404).json({ error: 'Job não encontrado' });
      res.json(job);
    } catch (err) {
      console.error('[obterJob]', err);
      res.status(500).json({ error: err.message });
    }
  }

  // ───────────────────────────────────────────────────────────────────────
  //  POST /api/jobs/analisar   Body: { pasta_raiz, num_job }
  // ───────────────────────────────────────────────────────────────────────
  async function analisarJob(req, res) {
    const { pasta_raiz, num_job } = req.body || {};

    if (!pasta_raiz || !num_job) {
      return res.status(400).json({ error: 'Campos obrigatórios: pasta_raiz, num_job' });
    }

    console.log(`\n[analisar] Iniciando: ${num_job} — ${pasta_raiz}`);

    const python = spawn(PYTHON_BIN, [...SCRIPT_ARGS_PREFIX, pasta_raiz], {
      env: { ...process.env, PYTHONUTF8: '1' },
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';

    python.stdout.on('data', chunk => { stdout += chunk.toString('utf8'); });
    python.stderr.on('data', chunk => {
      const line = chunk.toString('utf8');
      stderr += line;
      process.stdout.write(`[analisador] ${line}`);
    });

    python.on('error', err => {
      console.error('[spawn] Erro ao iniciar analisador:', err.message);
      return res.status(500).json({
        error: 'Não foi possível iniciar o analisador de documentos',
        detalhes: err.message,
      });
    });

    python.on('close', code => {
      let analise;
      try {
        const jsonStart = stdout.indexOf('{');
        if (jsonStart === -1) throw new Error('Nenhum JSON encontrado no stdout');
        analise = JSON.parse(stdout.slice(jsonStart));
      } catch (e) {
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

      const resultados = analise.resultados || [];
      const checklist = analise.checklist || [];

      const campo = id => {
        const r = resultados.find(x => x.id === id);
        return r?.valor || null;
      };
      const alertaAtivo = desc => {
        const c = checklist.find(x => x.descricao === desc);
        return c?.alerta ? 1 : 0;
      };

      try {
        const job = jobStore.upsert({
          num_job, pasta_raiz,
          contrato_existe: campo('contrato_existe'),
          procuracao_existe: campo('procuracao_existe'),
          honorarios: campo('honorarios'),
          gross_up: campo('gross_up'),
          passivo: campo('passivo'),
          data_abertura: campo('data_abertura'),
          simples_nacional: campo('simples_nacional'),
          socios: campo('socios'),
          situacao_fiscal: campo('situacao_fiscal'),
          regularize: campo('regularize'),
          perfil: campo('perfil'),
          faturamento: campo('faturamento'),
          fastpass: campo('fastpass'),
          supply: campo('supply'),
          finap: campo('finap'),
          alerta_sem_contrato: alertaAtivo('SEM CONTRATO'),
          alerta_sem_procuracao: alertaAtivo('SEM PROCURAÇÃO'),
          alerta_baixo_fat: alertaAtivo('FATURAMENTO MÉDIO ABAIXO DE R$ 20M'),
          alerta_regularize: alertaAtivo('COM REGULARIZE'),
          raw_resultado: analise, // objeto, não string — o frontend espera isso
        });

        console.log(`[analisar] Salvo — id: ${job.id}`);
        res.status(201).json({ mensagem: 'Análise concluída e salva com sucesso', job });
      } catch (dbErr) {
        console.error('[analisar] Erro ao salvar:', dbErr.message);
        res.status(207).json({
          mensagem: 'Análise concluída, mas não foi possível salvar',
          erro_banco: dbErr.message,
          analise,
        });
      }
    });
  }

  return { listarJobs, obterJob, analisarJob };
}

module.exports = { createController };
