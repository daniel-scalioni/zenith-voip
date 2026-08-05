# Cross-check: Registro de troncos ATA

> Data: `2026-08-01`
> Feature: `012-trunk-registration`
> Artefatos: `requirements.md`, `roadmap.md`, `actions.md`
> Modo: auditoria estritamente leitora
> Rodada: 2, após revisão do plano

## Resumo

| Severidade | Quantidade |
|------------|------------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

Veredito: **aprovado para quality/coding**.

## Findings

Nenhum finding aberto.

## Achados da rodada anterior resolvidos

| ID anterior | Resolução verificada |
|-------------|----------------------|
| A001 | O backend exclusivo agora inclui `LegacyDirectoryProvider`, testes Red, implementação e gate de equivalência/registro legado antes da ativação. |
| A002 | O plano agora exige `.example` sem segredo e renderer Red → Green que gera o arquivo real gitignored, atômico e modo 0600. |
| A003 | Roadmap e data-delta agora usam unicidade incondicional `(sip_profile, auth_username)`, complementada por detecção de colisão legada. |
| A004 | T005 deixou de ser paralela a T004; nenhuma tarefa `[//]` compartilha arquivo alvo. |

## Itens verificados que passaram

### Cobertura

- RF-01 a RF-12 possuem decisão e uma ou mais ações.
- Todos os cenários Gherkin têm cobertura Red e/ou E2E correspondente.
- Os quatro contratos externos constam no roadmap e em actions.
- A coexistência dos usuários legados possui contrato, teste, implementação e gate real.
- A entrega privada da credencial Basic possui teste antes da implementação.

### Consistência

- Hierarquia, perfis, estados e nomenclatura são estáveis nos documentos.
- Não há identificadores fantasmas.
- Unicidade de identidade possui a mesma semântica no roadmap, data-delta e actions.
- Configuração real e `.example` possuem papéis distintos e explícitos.

### Coerência com o legado

- Registros atuais de `extensions.xml` são preservados pelo provider somente leitura.
- Profiles 5060/7060 são alvos; 5062 e upstream permanecem protegidos.
- Tenant/PBX públicos e Repository são reutilizados.
- Variáveis globais só deixam de ser usadas após prova dos metadados autenticados.

### Sanidade do actions

- 55 ações identificadas; 22 marcadas `[//]`.
- Todas as dependências apontam para IDs existentes.
- Nenhum ciclo de dependência foi encontrado.
- Nenhuma tarefa paralela compartilha arquivo alvo.
- Specs e testes Red antecedem migrations, serviços, adapters e configuração Green.

## Histórico

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-01 | Rodada 1: 1 CRITICAL, 1 HIGH, 2 MEDIUM | reversa |
| 2026-08-01 | Rodada 2: achados resolvidos; aprovado sem findings | reversa |
