CREATE TABLE IF NOT EXISTS jobs_pro (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  num_job           TEXT    NOT NULL,                 -- Identificador do job (ex: 001 - EMPRESA)
  pasta_raiz        TEXT    NOT NULL,                 -- Caminho completo analisado

  -- ── Contrato ──────────────────────────────────────────────────────────────
  contrato_existe   TEXT,                              -- Sim — <arquivo> | nulo se não encontrado
  procuracao_existe TEXT,                              -- Sim — <arquivo> | nulo se não encontrado
  honorarios        TEXT,                              -- Percentual extraído do contrato
  gross_up          TEXT,                              -- Gross up extraído do contrato
  passivo           TEXT,                              -- Menção a passivos (booleano)

  -- ── QSA / Receita Federal ─────────────────────────────────────────────────
  data_abertura     TEXT,                              -- Data de constituição (CNPJ Matriz)
  simples_nacional  TEXT,                              -- Situação no Simples Nacional
  socios            TEXT,                              -- Sócios e administradores (múltiplos)

  -- ── Situação Fiscal ───────────────────────────────────────────────────────
  situacao_fiscal   TEXT,                              -- Tipo de certidão federal
  regularize        TEXT,                              -- SIM se arquivo REGULARIZE encontrado

  -- ── Perfil Previdenciário ─────────────────────────────────────────────────
  perfil            TEXT,                              -- Acima ou abaixo do limiar prev.

  -- ── Faturamento ───────────────────────────────────────────────────────────
  faturamento       TEXT,                              -- Totais por ano (ECF)
  fastpass          TEXT,                              -- Sim/Não — média >= R$20M
  supply            TEXT,                              -- Sim/Não — média >= R$30M
  finap             TEXT,                              -- Sim/Não — média >= R$50M e indústria

  -- ── Checklist de alertas ──────────────────────────────────────────────────
  alerta_sem_contrato   INTEGER NOT NULL DEFAULT 0,
  alerta_sem_procuracao INTEGER NOT NULL DEFAULT 0,
  alerta_baixo_fat      INTEGER NOT NULL DEFAULT 0,
  alerta_regularize     INTEGER NOT NULL DEFAULT 0,

  -- ── Resultado completo (JSON bruto para debug) ────────────────────────────
  raw_resultado     TEXT,                              -- Array completo retornado pelo analisador (JSON serializado)

  -- ── Status da análise ─────────────────────────────────────────────────────
  status_analise    TEXT    NOT NULL DEFAULT 'ok',     -- 'ok' | 'erro'
  erro_msg          TEXT,                              -- Mensagem de erro se status = erro

  analisado_em      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
  created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
  updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_num_job_unique ON jobs_pro (num_job);
CREATE INDEX IF NOT EXISTS idx_analisado_em ON jobs_pro (analisado_em);

-- Mantém updated_at em dia a cada UPDATE (SQLite não tem "ON UPDATE CURRENT_TIMESTAMP" nativo)
CREATE TRIGGER IF NOT EXISTS trg_jobs_pro_updated_at
AFTER UPDATE ON jobs_pro
FOR EACH ROW
BEGIN
  UPDATE jobs_pro SET updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime') WHERE id = NEW.id;
END;
