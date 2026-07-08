# Onboarding: Testar a Detecção Dinâmica de IP Externo

> Feature: `005-dynamic-external-ip`
> Pré-requisitos: Docker Compose rodando com FreeSWITCH, acesso ao `fs_cli`

## Ambiente dev (com MOCK)

1. Garanta que o serviço `ip-watcher` está no `docker-compose.app.yml`
2. Configure no `.env`:
   ```
   EXTERNAL_IP_ENDPOINT=http://localhost:9999  # não usado em mock
   MOCK_EXTERNAL_IP=189.112.222.244
   ESL_PASSWORD=ClueCon  # ou a senha configurada
   ```
3. Suba o sidecar:
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d ip-watcher
   ```
4. Verifique os logs:
   ```bash
   docker compose logs -f ip-watcher
   ```
   Deve exibir: `ip_anterior=None, ip_atual=189.112.222.244, acao_tomada=startup`

5. Confirme o IP no FreeSWITCH:
   ```bash
   docker compose exec freeswitch fs_cli -x "sofia status profile upstream"
   ```
   O campo `Ext-SIP-IP` deve mostrar `189.112.222.244`.

6. Simule uma mudança de IP editando o `.env` e reiniciando o sidecar:
   ```bash
   # No .env, altere:
   # MOCK_EXTERNAL_IP=200.200.200.200
   docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d ip-watcher
   ```
   Verifique nos logs: `ip_anterior=189.112.222.244, ip_atual=200.200.200.200, acao_tomada=update`

7. Confirme que o internal não foi afetado:
   ```bash
   docker compose exec freeswitch fs_cli -x "sofia status profile internal"
   ```
   O profile deve continuar ativo com os registros intactos.

## Ambiente produção/staging (sem mock)

1. Configure o endpoint real:
   ```
   EXTERNAL_IP_ENDPOINT=http://services.akom.com.br
   # NÃO setar MOCK_EXTERNAL_IP
   ESL_PASSWORD=<senha real>
   ```
2. Verifique se o BunkerWeb tem a regra DNAT:
   ```
   UDP 5065 → 10.10.10.11:5065
   ```
3. Suba o sidecar (mesmo comando do passo 3 acima)
4. Acompanhe os logs até a primeira verificação (60s)
5. Validar:
   - `docker compose exec freeswitch fs_cli -x "sofia status profile upstream"` mostra IP público
   - Gateways upstream saem de FAIL_WAIT e vão para REGED

## Rollback

```bash
docker compose stop ip-watcher && docker compose rm -f ip-watcher
```

Remover o serviço do `docker-compose.app.yml` e fazer `docker compose down && docker compose up -d` para limpeza completa.

## Histórico

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial | reversa |
