const fs       = require('fs');
const path     = require('path');
const Database = require('better-sqlite3');

let db;

// Caminho do arquivo do banco.
// Por padrão, fica ao lado do executável/projeto, em data/database.sqlite
// (pode ser sobrescrito via DB_FILE no .env, útil para apontar para um
// caminho de rede compartilhado entre várias instâncias, se necessário).
function resolverCaminhoDB() {
  if (process.env.DB_FILE) return process.env.DB_FILE;
  // path.dirname(process.execPath) seria a pasta do .exe quando empacotado
  // com pkg; aqui usamos __dirname para funcionar igual em dev e empacotado,
  // já que o pkg resolve __dirname para dentro do snapshot — então usamos a
  // pasta do processo quando empacotado (process.pkg) e __dirname em dev.
  const baseDir = process.pkg ? path.dirname(process.execPath) : path.join(__dirname, '..');
  return path.join(baseDir, 'data', 'database.sqlite');
}

function getDB() {
  if (!db) {
    const dbPath = resolverCaminhoDB();
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

async function iniciarDB() {
  const conn = getDB();

  // Lê e executa a migration inicial (idempotente: usa IF NOT EXISTS)
  const sql = fs.readFileSync(path.join(__dirname, '../migrations/001_init.sql'), 'utf8');
  conn.exec(sql);

  // Bancos já existentes: adiciona colunas novas que não existiam ainda
  const novas = { supply: 'TEXT', finap: 'TEXT' };
  const cols = conn.prepare('PRAGMA table_info(jobs_pro)').all();
  const existentes = new Set(cols.map(c => c.name));
  for (const [nome, tipo] of Object.entries(novas)) {
    if (!existentes.has(nome)) {
      conn.exec(`ALTER TABLE jobs_pro ADD COLUMN ${nome} ${tipo}`);
      console.log(`[DB] Coluna adicionada: ${nome}`);
    }
  }

  console.log('[DB] Tabelas verificadas/criadas com sucesso');
}

module.exports = { getDB, iniciarDB };
