# Interface privada: Configuração de tronco VitalPBX

> Fonte: exportação manual do VitalPBX. Veículo transitório de transferência GPhone → Zenith, não formato canônico do projeto: depois da importação a fonte de verdade é o banco e o arquivo é descartado.

## Entrada aceita

Duas formas do mesmo veículo:

1. **Documento único** — JSON UTF-8 com objetos `configuracoes_gerais` e `general_configurations`.
2. **Lote** — JSON UTF-8 com `ramais[]`; cada item traz `numero`, `tecnologia` e as credenciais em `configuracoes.autenticacao_e_rede`, com os mesmos campos de conexão do documento único.

Regras comuns às duas formas:

- O nome do condomínio é informado separadamente e de forma explícita; não é inferido da descrição. No lote, o chamador passa o mapa `numero → condominium_name`, e um `numero` sem entrada no mapa rejeita a importação.
- `tecnologia=PJSIP` e `porta=7060` mapeiam para `sip_profile=internal-7060` e transporte UDP.
- `nome_de_usuario_remoto` é a identidade canônica; `nome_de_usuario_de_saida` deve coincidir quando preenchido.
- `segredo_remoto` é a credencial canônica; `segredo_local` deve coincidir quando preenchido.
- `prefix` é sempre `null` nesta fonte; login, descrição e número discado nunca são convertidos em prefixo.
- `enabled` é sempre `false` no primeiro cadastro.

## Saída normalizada

O adaptador produz uma linha equivalente ao contrato interno de tronco com:

- `condominium_name` explícito;
- `prefix=null`;
- `auth_username`;
- `password` somente em memória e oculto de `repr`/erros;
- `sip_profile=internal-7060`;
- `enabled=false` na persistência.

## Falha fechada

Tecnologia/porta divergente, usuários inconsistentes, segredos inconsistentes, campos obrigatórios ausentes ou JSON inválido são rejeitados por código sanitizado. Nenhuma mensagem inclui valores de credencial ou o documento bruto.

No lote a rejeição é tudo-ou-nada: um único item inválido aborta a importação inteira antes de qualquer cifra ou persistência. O erro identifica a posição do item no arquivo, nunca o conteúdo dele.

## Roteamento preservado

- Central → condomínio: o VitalPBX recebe a discagem externa (exemplo `1020100`), aplica suas regras e o Zenith encaminha ao ATA apenas o destino resultante observado.
- Condomínio → central: o ATA/PABX entrega o número discado (exemplo `100`) e o Zenith o encaminha sem alteração ao VitalPBX.
- O valor `1020` identifica a credencial SIP; nenhuma regra do Zenith o remove, acrescenta ou interpreta como prefixo.
