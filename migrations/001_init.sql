CREATE TABLE IF NOT EXISTS jobs_pro (
  id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  num_job           VARCHAR(100)   NOT NULL COMMENT 'Identificador do job (ex: 001 - EMPRESA)',
  pasta_raiz        VARCHAR(1000)  NOT NULL COMMENT 'Caminho completo analisado',

  -- ── Contrato ──────────────────────────────────────────────────────────────
  contrato_existe   TEXT           COMMENT 'Sim — <arquivo> | nulo se não encontrado',
  procuracao_existe TEXT           COMMENT 'Sim — <arquivo> | nulo se não encontrado',
  honorarios        TEXT           COMMENT 'Percentual extraído do contrato',
  gross_up          TEXT           COMMENT 'Gross up extraído do contrato',
  passivo           TEXT           COMMENT 'Menção a passivos (booleano)',

  -- ── QSA / Receita Federal ─────────────────────────────────────────────────
  data_abertura     TEXT           COMMENT 'Data de constituição (CNPJ Matriz)',
  simples_nacional  TEXT           COMMENT 'Situação no Simples Nacional',
  socios            TEXT           COMMENT 'Sócios e administradores (múltiplos)',

  -- ── Situação Fiscal ───────────────────────────────────────────────────────
  situacao_fiscal   TEXT           COMMENT 'Tipo de certidão federal',
  regularize        TEXT           COMMENT 'SIM se arquivo REGULARIZE encontrado',

  -- ── Perfil Previdenciário ─────────────────────────────────────────────────
  perfil            TEXT           COMMENT 'Acima ou abaixo do limiar prev.',

  -- ── Faturamento ───────────────────────────────────────────────────────────
  faturamento       TEXT           COMMENT 'Totais por ano (ECF)',
  fastpass          TEXT           COMMENT 'Sim/Não — média >= R$20M',

  -- ── Checklist de alertas ──────────────────────────────────────────────────
  alerta_sem_contrato   TINYINT(1) DEFAULT 0,
  alerta_sem_procuracao TINYINT(1) DEFAULT 0,
  alerta_baixo_fat      TINYINT(1) DEFAULT 0,
  alerta_regularize     TINYINT(1) DEFAULT 0,

  -- ── Resultado completo (JSON bruto para debug) ────────────────────────────
  raw_resultado     JSON           COMMENT 'Array completo retornado pelo analisador',

  -- ── Status da análise ─────────────────────────────────────────────────────
  status_analise    ENUM('ok','erro') NOT NULL DEFAULT 'ok',
  erro_msg          TEXT           COMMENT 'Mensagem de erro se status = erro',

  analisado_em      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX idx_num_job (num_job),
  INDEX idx_analisado_em (analisado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
