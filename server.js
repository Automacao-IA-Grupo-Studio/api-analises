require('dotenv').config();
const express = require('express');
const cors    = require('cors');
const path    = require('path');
const routes  = require('./routes/api.routes');
const { iniciarDB, getPool } = require('./db/connection');

const app  = express();
const PORT = process.env.PORT || 3030;

app.use(cors());
app.use(express.json());

// Healthcheck: confirma que a API está de pé e o MySQL (no Docker) responde
app.get('/health', async (req, res) => {
  try {
    await getPool().query('SELECT 1');
    res.json({ status: 'ok', db: 'ok' });
  } catch (err) {
    res.status(503).json({ status: 'error', db: 'down', message: err.message });
  }
});

// Frontend estático
app.use(express.static(path.join(__dirname, 'frontend')));

// Rotas da API
app.use('/api', routes);

// Fallback: serve index.html para qualquer rota não-API
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

// Inicializa banco e sobe servidor
iniciarDB()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`\n╔═══════════════════════════════════════╗`);
      console.log(`║   API Análises — Studio Fiscal        ║`);
      console.log(`╚═══════════════════════════════════════╝`);
      console.log(`\n  ▶  http://localhost:${PORT}`);
      console.log(`  ▶  http://localhost:${PORT}/api/jobs\n`);
    });
  })
  .catch(err => {
    console.error('[FATAL] Erro ao inicializar banco:', err.message || err);
    console.error('[FATAL] Detalhes:', err);
    process.exit(1);
  });
