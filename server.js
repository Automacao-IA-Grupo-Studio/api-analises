require('dotenv').config();
const express = require('express');
const cors    = require('cors');
const path    = require('path');
const routes  = require('./routes/api.routes');
const { iniciarDB, getPool } = require('./db/connection');
const logger  = require('./desktop-gui/server/logger');

// Logs do servidor: buffer em memória (tela /logs.html) + data/logs/app.log.
// Só escreve na pasta da aplicação — nunca nas pastas de rede analisadas.
logger.init(path.join(__dirname, 'data', 'logs'));
// Registra e mantém o comportamento padrão (encerrar): o PM2 reinicia a API.
process.on('uncaughtException', err => { logger.erro('[main] uncaughtException:', err); process.exit(1); });
process.on('unhandledRejection', err => { logger.erro('[main] unhandledRejection:', err); process.exit(1); });

const app  = express();
const PORT = process.env.PORT || 3030;

app.use(cors());
app.use(express.json());

// Registra toda chamada de API que deu erro (4xx/5xx). O polling da tela de
// logs fica de fora para não poluir.
app.use('/api', (req, res, next) => {
  res.on('finish', () => {
    if (res.statusCode >= 400 && !req.originalUrl.startsWith('/api/logs')) {
      logger.aviso(`[http] ${req.method} ${req.originalUrl} -> ${res.statusCode}`);
    }
  });
  next();
});

// Healthcheck: confirma que a API está de pé e o MySQL (no Docker) responde
app.get('/health', async (req, res) => {
  try {
    await getPool().query('SELECT 1');
    res.json({ status: 'ok', db: 'ok' });
  } catch (err) {
    res.status(503).json({ status: 'error', db: 'down', message: err.message });
  }
});

// Tela de logs escondida (Ctrl+Shift+L no dashboard, ou direto em /logs.html).
// O arquivo é o mesmo do Modo Desktop — fica em um só lugar.
app.get('/api/logs', (req, res) => res.json({
  ...logger.listar(parseInt(req.query.desde, 10) || 0),
  arquivo: logger.caminhoArquivo(),
}));
app.post('/api/logs/limpar', (req, res) => { logger.limparTela(); res.json({ ok: true }); });
app.get('/logs.html', (req, res) => res.sendFile(path.join(__dirname, 'desktop-gui', 'frontend', 'logs.html')));

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
      logger.info(`API iniciada na porta ${PORT} | node=${process.versions.node} | ${process.platform}/${process.arch}`);
    });
  })
  .catch(err => {
    logger.erro('[FATAL] Erro ao inicializar banco:', err);
    process.exit(1);
  });
