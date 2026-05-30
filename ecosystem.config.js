module.exports = {
  apps: [
    {
      name: 'ura-panel',
      script: './ura_panel.py',
      interpreter: 'python3',
      cwd: '/Users/ramonesnaola/URA/ura_ia_1972',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: { NODE_ENV: 'production' },
      error_file: './logs/ura-panel-error.log',
      out_file: './logs/ura-panel-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'ura-verificador',
      script: './agents/agente_verificador_tareas.py',
      interpreter: '/Users/ramonesnaola/URA/ura_ia_1972/.venv/bin/python3',
      cwd: '/Users/ramonesnaola/URA/ura_ia_1972',
      args: '--daemon',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: { NODE_ENV: 'production' },
      error_file: './logs/ura-verificador-error.log',
      out_file: './logs/ura-verificador-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
