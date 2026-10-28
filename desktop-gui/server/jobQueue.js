// Compartilhado pela API e Desktop. A origem só recebe realpath/stat/readdir.
const fs = require('fs').promises;
const path = require('path');
const { randomUUID } = require('crypto');

function createQueue({ analyze, root = process.env.JOBS_ROOT || String.raw`\\studiofiscal\Temporarios`, concurrency = Number(process.env.JOBS_CONCURRENCY) || 2 }) {
  concurrency = Math.max(1, Math.min(4, Math.floor(concurrency)));
  const items = [];
  let active = 0;
  async function resolve(relative = '') {
    if (typeof relative !== 'string' || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) throw new Error('Pasta fora da raiz permitida');
    const base = await fs.realpath(root);
    const target = await fs.realpath(path.join(base, relative));
    const rel = path.relative(base, target);
    if (rel === '..' || rel.startsWith('..' + path.sep) || path.isAbsolute(rel)) throw new Error('Pasta fora da raiz permitida');
    if (!(await fs.stat(target)).isDirectory()) throw new Error('Diretório inválido');
    return { target, relative: rel };
  }
  function pump() {
    while (active < concurrency) {
      const item = items.find(x => x.status === 'fila');
      if (!item) break;
      active++; item.status = 'processando';
      Promise.resolve().then(() => analyze({ pasta_raiz: item.pasta_raiz, num_job: item.num_job })).then(result => {
        item.status = 'concluido'; item.job_id = result?.job?.id;
      }, error => { item.status = 'erro'; item.error = error.message; }).finally(() => { active--; pump(); });
    }
  }
  async function enqueue(jobs) {
    if (!Array.isArray(jobs) || !jobs.length || jobs.length > 200) throw new Error('Selecione de 1 a 200 jobs');
    const checked = await Promise.all(jobs.map(async job => {
      const relative = typeof job.pasta_raiz === 'string' ? path.relative(path.resolve(root), path.resolve(job.pasta_raiz)) : job.relative;
      if (typeof relative !== 'string') throw new Error('Pasta obrigatória');
      const resolved = await resolve(relative);
      if (!resolved.relative) throw new Error('Selecione uma pasta de job');
      return { ...resolved, num_job: path.basename(resolved.target) };
    }));
    const accepted = [];
    for (const job of checked) {
      let item = items.find(x => ['fila', 'processando'].includes(x.status) && x.pasta_raiz === job.target);
      if (!item) {
        // Histórico da fila é transitório e limitado; resultados permanecem no armazenamento habitual.
        if (items.length >= 1000) {
          const old = items.findIndex(x => !['fila','processando'].includes(x.status));
          if (old >= 0) items.splice(old, 1);
          else throw new Error('Fila cheia');
        }
        item = { id: randomUUID(), num_job: job.num_job, pasta_raiz: job.target, status: 'fila' };
        items.push(item);
      }
      accepted.push(item);
    }
    pump(); return accepted;
  }
  return {
    enqueue,
    list: () => ({ items: items.map(x => ({ ...x })), concurrency }),
    async browse(relative) {
      const folder = await resolve(relative);
      const entries = await fs.readdir(folder.target, { withFileTypes: true });
      return { root, relative: folder.relative, folders: entries.filter(x => x.isDirectory() && !x.isSymbolicLink()).map(x => ({ name: x.name, relative: path.join(folder.relative, x.name) })).sort((a,b) => a.name.localeCompare(b.name, 'pt-BR', { numeric: true })) };
    },
  };
}

function mountQueue(router, controller) {
  const queue = createQueue({ analyze: body => new Promise((resolve, reject) => {
    let status = 200, done = false;
    const response = { status(code) { status = code; return this; }, json(data) {
      if (done) return; done = true;
      if (status >= 400 || data.erro_banco) reject(new Error(data.error || data.mensagem || 'Falha na análise'));
      else resolve(data);
    } };
    Promise.resolve(controller.analisarJob({ body }, response)).catch(reject);
  }) });
  router.get('/pastas', async (req,res) => {
    try { res.json(await queue.browse(req.query.relative || '')); }
    catch (e) { res.status(400).json({ error: e.message }); }
  });
  router.get('/fila', (req,res) => res.json(queue.list()));
  router.post('/fila', async (req,res) => {
    try { res.status(202).json({ items: await queue.enqueue(req.body?.jobs) }); }
    catch (e) { res.status(400).json({ error: e.message }); }
  });
  return queue;
}
module.exports = { createQueue, mountQueue };
