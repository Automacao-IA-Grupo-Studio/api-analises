const mysql = require('mysql2/promise');

let pool;

function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      host:     process.env.DB_HOST || 'localhost',
      port:     parseInt(process.env.DB_PORT || '3306'),
      user:     process.env.DB_USER || 'root',
      password: process.env.DB_PASS || 'studiofiscal',
      database: process.env.DB_NAME || 'api_analises',
      waitForConnections: true,
      connectionLimit:    10,
      timezone: '-03:00',
    });
  }
  return pool;
}

async function iniciarDB() {
  const conn = await getPool().getConnection();
  try {
    // Lê e executa a migration inicial se as tabelas não existirem
    const fs   = require('fs');
    const path = require('path');
    const sql  = fs.readFileSync(path.join(__dirname, '../migrations/001_init.sql'), 'utf8');
    // Executa cada statement separado por ;
    const statements = sql
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0);
    for (const stmt of statements) {
      await conn.query(stmt);
    }
    // Bancos já existentes: adiciona colunas novas (MySQL não tem ADD COLUMN IF NOT EXISTS)
    const novas = { supply: 'TEXT NULL', finap: 'TEXT NULL' };
    const [cols] = await conn.query('SHOW COLUMNS FROM jobs_pro');
    const existentes = new Set(cols.map(c => c.Field));
    for (const [nome, tipo] of Object.entries(novas)) {
      if (!existentes.has(nome)) {
        await conn.query(`ALTER TABLE jobs_pro ADD COLUMN ${nome} ${tipo}`);
        console.log(`[DB] Coluna adicionada: ${nome}`);
      }
    }
    console.log('[DB] Tabelas verificadas/criadas com sucesso');
  } finally {
    conn.release();
  }
}

module.exports = { getPool, iniciarDB };
