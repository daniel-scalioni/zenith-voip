# Spike: escrita controlada no storage SMB

> Feature: `011-smb-audio-backup`
> Data: `2026-07-28`
> Estado: concluído — operações manuais e cliente Python confirmados
> Regra: nunca registrar credenciais ou conteúdo do `.env`

## Objetivo

Validar o ambiente SMB antes da implementação do worker: conectividade, Direct TCP/445, nome NetBIOS, autenticação da conta técnica, share/path, criação, escrita, leitura, rename e remoção.

O resultado servirá como evidência para refinar requirements, roadmap, interface, onboarding e actions da feature 011.

## Preflight executado

| Verificação | Resultado |
|-------------|-----------|
| TCP `192.168.50.240:445` | acessível |
| `.env` existe | sim |
| Chaves `SMB_*` no `.env` | presentes (valores não inspecionados) |
| `smbclient` local | ausente |
| pacote Python `pysmb` local | `1.2.14` instalado no ambiente isolado |
| Escrita remota executada | sim, confirmada manualmente pelo usuário |

Nenhum valor do `.env` foi lido ou exibido pelo agente. O usuário confirmou que o protocolo
manual de criação, escrita, leitura, rename e remoção funcionou no storage.

## Configuração necessária

O `.env` privado deve conter:

```dotenv
SMB_ENABLED=true
SMB_HOST=192.168.50.240
SMB_PORT=445
SMB_IS_DIRECT_TCP=true
SMB_CLIENT_NAME=ZENITH
SMB_SERVER_NAME=<nome-netbios-real>
SMB_DOMAIN=
SMB_USE_NTLM_V2=true
SMB_SHARE=<share>
SMB_PATH=<pasta-base>
SMB_USERNAME=<conta-tecnica-write>
SMB_PASSWORD=<segredo>
```

A conta técnica precisa de `mkdir`, write, read, rename e delete apenas na pasta destinada ao Zenith. A credencial READ-ONLY dos auditores é separada e não entra no `.env`.

## Protocolo do teste

1. Instalar/usar `pysmb==1.2.14` no ambiente isolado do projeto.
2. Validar a combinação `SMB_IS_DIRECT_TCP=true` + porta 445.
3. Conectar usando `SMB_CLIENT_NAME` e `SMB_SERVER_NAME`, sem logar credenciais.
4. Criar um subdiretório dedicado ao spike, se permitido:

   ```text
   {SMB_PATH}/_zenith_spike/
   ```

5. Criar arquivo temporário com nome único:

   ```text
   zenith-write-test-<timestamp>-<nonce>.tmp
   ```

6. O conteúdo será texto aleatório não sensível, sem áudio ou dado pessoal.
7. Ler o arquivo de volta e comparar SHA256.
8. Renomear `.tmp` para `.verified`.
9. Ler novamente e confirmar o mesmo SHA256.
10. Remover `.verified`.
11. Confirmar que o arquivo não existe mais.
12. Tentar remover o diretório `_zenith_spike` se estiver vazio.

## Segurança e recuperação

- O teste usa somente a conta técnica WRITE.
- Não usa a conta dos auditores.
- Não sobrescreve nomes existentes.
- Se qualquer etapa falhar, registrar apenas classe/etapa do erro, nunca senha.
- Se a remoção falhar, interromper e informar o caminho exato do artefato residual ao usuário.
- Não testar fora de `{SMB_PATH}/_zenith_spike/`.

## Evidências a preencher

| Evidência | Resultado |
|-----------|-----------|
| conexão/autenticação | confirmado manualmente e via `pysmb==1.2.14` |
| share/path acessível | confirmado manualmente |
| mkdir | confirmado manualmente |
| write | confirmado manualmente |
| read + SHA256 | confirmado antes e depois do rename |
| rename | confirmado manualmente e via `pysmb` |
| delete | confirmado manualmente e via `pysmb` |
| cleanup do diretório | arquivo removido; remoção do diretório tentada quando vazio |
| parâmetros confirmados | Direct TCP/445, nome remoto, NTLMv2 e assinatura `SIGN_WHEN_REQUIRED` funcionais |
| escrita por offset | dois chunks confirmados: offset 0 com truncate e offset seguinte sem truncate |
| observações do servidor | compatível com `pysmb==1.2.14`; nenhum resíduo de arquivo detectado |

## Critério para retomar o forward

O `/reversa-plan` pode ser retomado com as evidências acima. Permanecem para o E2E:

1. validação negativa da conta READ-ONLY dos auditores;
2. ausência de resíduos após falhas induzidas no worker final.

## Execução automatizada — 2026-07-28

O mini-spike usou conteúdo aleatório não sensível e nome com nonce. Foram confirmados:

- conexão Direct TCP/445 com `pysmb==1.2.14`;
- `sign_options=2`;
- dois chunks via `storeFileFromOffset`;
- SHA256 idêntico antes e depois do rename;
- remoção do arquivo remoto e ausência de resíduo.

Nenhum valor do `.env`, hash real ou nome remoto foi registrado.
