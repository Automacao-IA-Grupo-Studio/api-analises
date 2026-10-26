// ─────────────────────────────────────────────────────────────────────────────
// Config do PM2 — mantém a API (server.js) rodando na VM fora do Docker.
//
// Uso (dentro da pasta do projeto, na VM):
//   pm2 start ecosystem.config.js     # inicia
//   pm2 save                          # grava a lista p/ sobreviver a reboot
//   pm2 startup                       # (uma vez) registra o PM2 como serviço do SO
//   pm2 logs api-analises             # acompanha os logs
//   pm2 restart api-analises          # reinicia (ex.: depois de um git pull)
//   pm2 status                        # ver se está no ar
//
// A API fica em http://<IP-DA-VM>:3030 — é essa porta que o resto da rede usa.
// ─────────────────────────────────────────────────────────────────────────────
module.exports = {
  apps: [
    {
      name:         'api-analises',
      script:       'server.js',
      cwd:          __dirname,
      instances:    1,
      exec_mode:    'fork',
      autorestart:  true,
      watch:        false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        NODE_ENV: 'production',
        PORT:     process.env.PORT || 3030,
      },
      out_file:  './logs/pm2-out.log',
      error_file: './logs/pm2-error.log',
      time:      true,
    },
  ],
};
