const {test} = require('node:test');
const assert = require('node:assert/strict');
const logger = require('../desktop-gui/server/logger');

test('formatarDuracao: segundos, minutos e horas', () => {
  assert.equal(logger.formatarDuracao(0), '0,0 s');
  assert.equal(logger.formatarDuracao(12_340), '12,3 s');
  assert.equal(logger.formatarDuracao(59_900), '59,9 s');
  assert.equal(logger.formatarDuracao(60_000), '1 min 00 s');
  assert.equal(logger.formatarDuracao(20 * 60_000 + 3_000), '20 min 03 s');
  assert.equal(logger.formatarDuracao(3_720_000), '1 h 02 min');
  assert.equal(logger.formatarDuracao(-5), '0,0 s');
});

test('listar devolve só as linhas novas, com timestamp ISO', () => {
  logger.limparTela();
  const a = logger.info('primeira');
  logger.aviso('segunda');
  const novas = logger.listar(a.id).linhas;
  assert.equal(novas.length, 1);
  assert.equal(novas[0].nivel, 'AVISO');
  assert.ok(!Number.isNaN(Date.parse(novas[0].ts)));
  logger.limparTela();
});
