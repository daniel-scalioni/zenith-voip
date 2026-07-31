# Interface: SMB/CIFS Audio Backup

> Identificador: `011-smb-audio-backup`
> Tipo: Arquivo de rede
> Biblioteca cliente: `pysmb==1.2.14`
> Data: `2026-07-27`

## Endpoint lógico

```text
\\{SMB_HOST}\{SMB_SHARE}\{SMB_PATH}\
└── {tenant}\
    └── {YYYY-MM-DD}\
        └── {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3
```

O destino contém um MP3 estéreo: canal esquerdo=`tx` (agente), canal direito=`rx` (cliente).

## Configuração

| Campo | Default | Obrigatoriedade |
|-------|---------|-----------------|
| `SMB_ENABLED` | `false` | sempre |
| `SMB_HOST` | vazio | quando habilitado |
| `SMB_PORT` | `445` | sempre |
| `SMB_IS_DIRECT_TCP` | `true` | sempre; `false` para porta 139 |
| `SMB_CLIENT_NAME` | `ZENITH` | NetBIOS local válido, até 15 caracteres |
| `SMB_SERVER_NAME` | vazio | obrigatório quando habilitado |
| `SMB_DOMAIN` | vazio | opcional |
| `SMB_USE_NTLM_V2` | `true` | sempre |
| `SMB_SIGN_OPTIONS` | `2` (`SIGN_WHEN_REQUIRED`) | sempre |
| `SMB_SHARE` | vazio | quando habilitado |
| `SMB_PATH` | vazio | permitido para raiz do share |
| `SMB_USERNAME` | vazio | quando habilitado |
| `SMB_PASSWORD` | vazio | quando habilitado; nunca logar |
| `SMB_BANDWIDTH_LIMIT_MBS` | `5` | valor positivo |
| `SMB_TRANSFER_LOG_PATH` | `/data/smb_logs/smb_transfer_log.json` | sempre |
| `SMB_SYNC_INTERVAL_MINUTES` | `5` | inteiro positivo |

## Operações

| Operação | Conta worker | Conta auditor |
|----------|---------------|---------------|
| connect/auth | permitido | permitido |
| mkdir | permitido | negado |
| store `.tmp` | permitido | negado |
| rename `.tmp` → final | permitido | negado |
| retrieve para checksum/leitura | permitido | permitido |
| delete temporário/corrompido | permitido | negado |

## Publicação

1. Produzir `stereo.mp3` local por rename atômico.
2. Calcular SHA256 local.
3. Criar diretórios remotos recursivamente.
4. Escrever `{remote_name}.tmp` em chunks com `storeFileFromOffset`: primeiro chunk com `offset=0, truncate=True`; seguintes com offset crescente e `truncate=False`.
5. Renomear para `{remote_name}`.
6. Ler remoto e calcular SHA256.
7. Se igual: marcar `done`.
8. Se divergente: remover remoto, manter `pending` e retentar.

Destino final existente:

- mesmo SHA256: sucesso idempotente;
- SHA256 diferente: tentar uma única vez o nome com sufixo `-{call_id[6:10]}`; se também colidir, não sobrescrever e registrar falha.

## Transporte e autenticação

`SMBConnection` recebe `my_name=SMB_CLIENT_NAME`, `remote_name=SMB_SERVER_NAME`, `use_ntlm_v2=SMB_USE_NTLM_V2`, `sign_options=SMB_SIGN_OPTIONS` e `is_direct_tcp=SMB_IS_DIRECT_TCP`. `connect` usa `SMB_HOST`, `SMB_PORT` e timeout.

- Direct TCP `true` → porta padrão 445.
- Direct TCP `false` → porta padrão 139.
- SMB2 é negociado automaticamente quando suportado.
- Compatibilidade real e política de autenticação são gates E2E.

## Timeouts e retry

| Operação | Timeout |
|----------|--------:|
| conexão/autenticação | 10 s |
| operação individual | 30 s |
| geração estéreo + arquivo completo | 30 s globais |

Falhas transitórias: até três tentativas com espera 1s, 2s e 4s. Após cinco falhas consecutivas do processo, circuit breaker suspende novas cópias por 5 min.

Erros de configuração/autenticação não entram em retry rápido; geram falha observável até correção.

## Throttle

Um único processo `zenith-smb-sync` executa uma operação por vez. O limiter de módulo compartilha bytes/tempo entre todos os chunks desse processo. Não há promessa de coordenação entre réplicas; escalar horizontalmente exige nova decisão arquitetural.

Cada execução adquire um lock de ciclo com identificador estável. Se o lock estiver ativo, a execução
seguinte retorna `already_running`. Durante geração e transferência, o worker cria um lease local com
timestamp UTC, validade de 120 s e renovação a cada 30 s. O cleanup ignora lease válido; lease
expirado, inválido ou corrompido é tratado como expirado e gera alerta.

O orçamento de 30 s começa antes da geração do `stereo.mp3` e termina após o checksum remoto. Ao
expirar, a operação é interrompida de forma observável, permanece `pending` e nenhum arquivo final
sem checksum aprovado é aceito como concluído.

## Observabilidade e segurança

- Logs: `call_id`, `tenant_id`, status, bytes, latência, tentativa e classe sanitizada do erro.
- Nunca registrar username, password ou representação integral da conexão.
- Métricas: sucesso, falha, latência, fila e falha de conversão.
- Sem labels de `call_id` em Prometheus.
- Áudio trafega em LAN privada conforme decisão do requirements.

## Critérios do contrato

- Um arquivo remoto por chamada.
- Dois canais separáveis e com mapeamento fixo.
- Nome com seis caracteres do `call_id`; UUID completo permanece no log.
- Arquivo final nunca aparece parcial.
- Conta de auditoria não pode alterar prova.
