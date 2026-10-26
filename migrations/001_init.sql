CREATE TABLE IF NOT EXISTS jobs_pro (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  num_job           VARCHAR(255) NOT NULL,             -- Identificador do job (ex: 001 - EMPRESA)
  pasta_raiz        TEXT NOT NULL,                      -- Caminho completo analisado

  -- ── Contrato ──────────────────────────────────────────────────────────────
  contrato_existe   TEXT,                               -- Sim — <arquivo> | nulo se não encontrado
  procuracao_existe TEXT,                               -- Sim — <arquivo> | nulo se não encontrado
  honorarios        TEXT,                               -- Percentual extraído do contrato
  gross_up          TEXT,                               -- Gross up extraído do contrato
  passivo           TEXT,                               -- Menção a passivos (booleano)

  -- ── QSA / Receita Federal ─────────────────────────────────────────────────
  data_abertura     TEXT,                               -- Data de constituição (CNPJ Matriz)
  simples_nacional  TEXT,                               -- Situação no Simples Nacional
  socios            TEXT,                               -- Sócios e administradores (múltiplos)

  -- ── Situação Fiscal ───────────────────────────────────────────────────────
  situacao_fiscal   TEXT,                               -- Tipo de certidão federal
  regularize        TEXT,                               -- SIM se arquivo REGULARIZE encontrado

  -- ── Perfil Previdenciário ─────────────────────────────────────────────────
  perfil            TEXT,                               -- Acima ou abaixo do limiar prev.

  -- ── Faturamento ───────────────────────────────────────────────────────────
  faturamento       TEXT,                               -- Totais por ano (ECF)
  fastpass          TEXT,                               -- Sim/Não — média >= R$20M
  supply            TEXT,                               -- Sim/Não — média >= R$30M
  finap             TEXT,                               -- Sim/Não — média >= R$50M e indústria

  -- ── Checklist de alertas ──────────────────────────────────────────────────
  alerta_sem_contrato   TINYINT(1) NOT NULL DEFAULT 0,
  alerta_sem_procuracao TINYINT(1) NOT NULL DEFAULT 0,
  alerta_baixo_fat      TINYINT(1) NOT NULL DEFAULT 0,
  alerta_regularize     TINYINT(1) NOT NULL DEFAULT 0,

  -- ── Resultado completo (JSON bruto para debug) ────────────────────────────
  raw_resultado     LONGTEXT,                           -- Array completo retornado pelo analisador (JSON serializado)

  -- ── Status da análise ─────────────────────────────────────────────────────
  status_analise    VARCHAR(20) NOT NULL DEFAULT 'ok',  -- 'ok' | 'erro'
  erro_msg          TEXT,                                -- Mensagem de erro se status = erro

  analisado_em      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY idx_num_job_unique (num_job),
  KEY idx_analisado_em (analisado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
