# Backlog técnico

Problemas conhecidos e melhorias de infraestrutura ainda não feitos. O backlog de produto
(histórias `VBP-*`) fica em [`plano-monetizacao-comunidade.md`](plano-monetizacao-comunidade.md).

## Aberto

### TEC-1 · Uma rajada de acessos derruba todos os sites (healthcheck)

**Achado em:** 10/11/2026, testando as tags do GA com pedidos simultâneos.

- **Sintoma:** com 16 pedidos simultâneos, os quatro sites (PHP, Ruby, Lua, Java) passaram a
  responder **503 "no available server"** por 1 a 2 minutos e voltaram sozinhos.
- **Causa provável:** o healthcheck do container `web` (`web/Dockerfile` e
  `docker-compose.coolify.yml`) chama `/api/stats`, que consulta o MySQL remoto (cerca de
  0,5 s sem carga; a home leva cerca de 1,5 s). Sob carga ele passa do timeout de 5 s, o
  container fica *unhealthy* e o Traefik o tira do ar. Como todos os sites são o mesmo
  container ([`docs/deploy.md`](../deploy.md)), caem juntos. Basta um robô mais agressivo.
- **Proposta:**
  1. Rota `/healthz` sem banco (só confirma que o PHP responde) e o healthcheck apontando
     para ela: lentidão deixa de virar queda.
  2. Healthcheck mais tolerante (timeout de 10 s).
  3. Avaliar cache curto das páginas e da `/api/stats` (APCu ou cache da Cloudflare com
     TTL baixo) para reduzir as idas ao MySQL.
- **Atenção:** não repetir teste de carga em produção.
