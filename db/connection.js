const fs    = require('fs');
const path  = require('path');
const mysql = require('mysql2/promise');

let pool;

// ── Configuração de conexão (vem do .env — ver .env.example) ────────────────
// Em produção (VM), o MySQL roda num container Docker, mas a própria API
// roda FORA do Docker (via PM2), então conecta nele como se fosse um banco
// externo normal: host + porta publicada no docker-compose.yml.
function config() {
  return {
    host:               process.env.DB_HOST || '127.0.0.1',
    port:               Number(process.env.DB_PORT) || 3306,
    user:               process.env.DB_USER || 'api_analises',
    password:           process.env.DB_PASSWORD || 'api_analises',
    database:           process.env.DB_NAME || 'api_analises',
    waitForConnections: true,
    connectionLimit:    10,
    queueLimit:         0,
    dateStrings:        true, // devolve DATETIME como string, igual ao comportamento antigo do SQLite
    namedPlaceholders:  true, // permite usar :num_job, :pasta_raiz etc. nas queries do controller
  };
}

function getPool() {
  if (!pool) {
    pool = mysql.createPool(config());
  }
  return pool;
}

// Tenta conectar algumas vezes antes de desistir — útil porque na VM o
// container do MySQL pode ainda estar subindo quando a API (via PM2) já
// tenta iniciar.
async function aguardarMySQL(tentativas = 15, intervaloMs = 2000) {
  const p = getPool();
  for (let i = 1; i <= tentativas; i++) {
    try {
      await p.query('SELECT 1');
      return;
    } catch (err) {
      if (i === tentativas) throw err;
      console.log(`[DB] MySQL ainda não respondeu (tentativa ${i}/${tentativas}) — tentando de novo em ${intervaloMs / 1000}s...`);
      await new Promise(r => setTimeout(r, intervaloMs));
    }
  }
}

async function iniciarDB() {
  await aguardarMySQL();
  const p = getPool();

  // Lê e executa a migration inicial (idempotente: usa IF NOT EXISTS)
  const sql = fs.readFileSync(path.join(__dirname, '../migrations/001_init.sql'), 'utf8');
  const statements = sql
    .split(/;\s*(?:\r?\n|$)/)
    .map(s => s.trim())
    .filter(Boolean);
  for (const stmt of statements) {
    await p.query(stmt);
  }

  // Bancos já existentes: adiciona colunas novas que não existiam ainda
  const novas = { supply: 'TEXT', finap: 'TEXT' };
  const [cols] = await p.query(
    `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'jobs_pro'`
  );
  const existentes = new Set(cols.map(c => c.COLUMN_NAME));
  for (const [nome, tipo] of Object.entries(novas)) {
    if (!existentes.has(nome)) {
      await p.query(`ALTER TABLE jobs_pro ADD COLUMN ${nome} ${tipo}`);
      console.log(`[DB] Coluna adicionada: ${nome}`);
    }
  }

  console.log('[DB] Tabelas verificadas/criadas com sucesso (MySQL)');
}

module.exports = { getPool, iniciarDB };
