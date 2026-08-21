# Deploy, Tarefas

- [ ] T-01: Configurar Docker Compose (15 serviços) 🟢
- [ ] T-02: Configurar BunkerWeb + sticky session 🟢
- [ ] T-03: Implementar deploy.sh com rollback 🟢
- [ ] T-04: Build customizado do FreeSWITCH com `mod_audio_fork` (`freeswitch/Dockerfile`) 🟡 — pendente validação contra build real
- [ ] T-05: Provisionar `arq-uploader` + storage local de gravação (`scripts/setup-recording-mvp.sh`) 🟢
- [ ] T-06: Declarar o PostgreSQL promovido como serviço canônico `postgres`, preservando volume,
  DNS e credencial privada em todos os consumidores. 🟢
- [ ] TT-01: Validar por parsing dos Compose que container, volume, alias e `DATABASE_URL`
  permanecem alinhados ao cutover. 🟢
