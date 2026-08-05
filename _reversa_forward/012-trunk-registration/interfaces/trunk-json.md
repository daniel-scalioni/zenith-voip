# Interface privada: Configuração individual de tronco VitalPBX

> Fonte: exportação manual de um tronco quando o VitalPBX não oferece exportação em lote.

## Entrada aceita

- JSON UTF-8 com objetos `configuracoes_gerais` e `general_configurations`.
- O nome do condomínio é informado separadamente e de forma explícita; não é inferido da descrição.
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

## Roteamento preservado

- Central → condomínio: o VitalPBX recebe a discagem externa (exemplo `1020100`), aplica suas regras e o Zenith encaminha ao ATA apenas o destino resultante observado.
- Condomínio → central: o ATA/PABX entrega o número discado (exemplo `100`) e o Zenith o encaminha sem alteração ao VitalPBX.
- O valor `1020` identifica a credencial SIP; nenhuma regra do Zenith o remove, acrescenta ou interpreta como prefixo.
