// app.js — monta o Express app (rotas + frontend estático).
// Fábrica pura: não escuta porta nenhuma sozinha (quem faz isso é main.js
// ou, em teste headless, um pequeno script à parte) — facilita testar com
// supertest/curl sem precisar do Electron de verdade.

const express = require('express');
const cors = require('cors');
const path = require('path');
const jobStore = require('./jobStore');
const { createController } = require('./controller');

/**
 * @param {object} opts
 * @param {string} opts.baseDir      Pasta onde procurar analisar_job.exe.
 * @param {string} opts.pyScriptPath Caminho p/ services/analisar_job.py (dev).
 * @param {string} opts.dbFile       Caminho do arquivo jobs.json.
 * @param {string} opts.frontendDir  Pasta com o index.html a servir em "/".
 */
function createApp({ baseDir, pyScriptPath, dbFile, frontendDir }) {
  jobStore.init(dbFile);

  const controller = createController({ baseDir, pyScriptPath });

  const app = express();
  app.use(cors());
  app.use(express.json());

  app.get('/health', (req, res) => res.json({ status: 'ok', db: 'ok' }));

  app.get('/api/jobs', controller.listarJobs);
  app.get('/api/jobs/:id', controller.obterJob);
  app.post('/api/jobs/analisar', controller.analisarJob);

  app.use(express.static(frontendDir));
  app.get('/', (req, res) => res.sendFile(path.join(frontendDir, 'index.html')));

  return app;
}

module.exports = { createApp };
