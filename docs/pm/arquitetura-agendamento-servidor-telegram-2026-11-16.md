# Vagas PHP — Arquitetura para agendamento no servidor

**PM:** Hermes · **Data:** 16/11/2026 · **Status:** proposta v1
**Escopo:** tirar do PC local a responsabilidade de agendar e publicar as vagas no Telegram.
**Fora de escopo:** reescrever o coletor, mudar o produto, trocar o canal.

---

## 1. Diagnóstico

Hoje o fluxo depende demais do PC que roda o Hermes. Quando ele falha, o canal perde cadência.

### Problemas reais

1. **Ponto único de falha**: se o PC dorme, reinicia ou perde sessão, o envio para.
2. **Estado distribuído demais**: há cron local, sessão local e scripts locais.
3. **Operação manual demais**: o agendamento não deveria depender de alguém lembrar de ligar a máquina.

### O que já existe e pode ser reaproveitado

- o projeto já roda em Docker no servidor;
- o envio ao Telegram já é scriptável;
- o site e o coletor já têm estado persistido;
- o Telegram não exige interação humana para publicar.

**Leitura de PM:** o problema não é o Telegram em si; é a dependência operacional do PC. A solução certa é mover o *scheduler* para o servidor e deixar o PC só como ambiente de desenvolvimento/recuperação.

---

## 2. Proposta de arquitetura

### Arquitetura recomendada: **scheduler no servidor + worker no container do produto**

**Fluxo:**

1. **Cron do servidor** dispara em horários fixos.
2. O cron executa um comando dentro do ambiente de produção do `vagas-php`.
3. Esse comando chama o script de envio do Telegram.
4. O script lê a base de vagas da produção, monta o lote e publica.
5. O estado de envio fica persistido no servidor, dentro do volume do app.

### Componentes

- **Agendador do sistema**: cron/systemd timer no servidor.
- **Worker de publicação**: comando do projeto (`telegram-alert`).
- **Estado persistente**: arquivos/DB no volume do app.
- **Observabilidade**: log em arquivo + alerta em caso de falha.
- **Fallback**: reexecução manual no servidor com o mesmo comando.

### Por que esta é a melhor opção

- reduz o risco operacional;
- não depende do PC pessoal;
- reaproveita o que já está pronto;
- é simples de entender e de debugar;
- mantém o custo baixo.

---

## 3. Opções avaliadas

| Opção | Como funciona | ICE | Prós | Contras |
|---|---|---:|---|---|
| **A. Cron no servidor chamando o script do Telegram** | O servidor agenda e executa o comando de publicação | **9.2** | simples, barato, confiável, rápido de implantar | menos flexível que uma fila completa |
| **B. Worker dedicado + fila interna** | Job entra numa fila e um worker consome | **7.8** | mais robusto para crescer | mais peças, mais manutenção |
| **C. Continuar no PC atual** | Hermes local segue publicando | **2.1** | zero mudança imediata | continua quebrando quando o PC falha |

**Recomendação:** **A → B**.

Começar com o cron no servidor resolve o problema de hoje. A fila só vale se o volume ou a complexidade crescer.

---

## 4. Desenho recomendado

### Fase 1 — Mover o envio para o servidor

- agendar no servidor os horários do Telegram;
- executar o comando dentro do ambiente do `vagas-php`;
- manter o mesmo estado de dedupe e logs;
- validar que o envio sai sem depender do PC.

### Fase 2 — Tornar o fluxo resiliente

- registrar última execução com sucesso/falha;
- retry automático em caso de erro temporário;
- alerta quando uma janela falhar;
- idempotência para não repetir o mesmo lote.

### Fase 3 — Unificar automações

- colocar Telegram, LinkedIn e alertas sob o mesmo padrão de execução;
- cada canal continua com seu próprio estado, mas todos rodam no servidor.

---

## 5. Requisitos de implementação

### Funcionais

- publicar no Telegram sem depender do PC;
- respeitar a agenda atual;
- continuar com dedupe, agrupamento e mensagem mínima;
- registrar sucesso/falha por execução.

### Não funcionais

- idempotência;
- logs persistentes;
- baixo custo;
- recuperação manual simples;
- nenhuma credencial hardcoded.

---

## 6. Plano de implantação sugerido

### Etapa 1 — Agendamento no servidor

- criar o cron no servidor;
- apontar para o comando do projeto em produção;
- testar em dry-run;
- depois testar envio real em uma janela controlada.

### Etapa 2 — Monitoramento

- logar cada execução;
- marcar falha quando o envio não completar;
- disparar alerta se duas janelas seguidas falharem.

### Etapa 3 — Retirada do PC da rota crítica

- o PC fica apenas como backup / desenvolvimento;
- nenhuma publicação depende dele;
- o servidor vira a fonte de verdade operacional.

---

## 7. Riscos

| Risco | Severidade | Mitigação | Plano B |
|---|---|---|---|
| Cron no servidor falha | Alta | logs + retry + alerta | execução manual com o mesmo comando |
| Estado de envio corrompe | Alta | backup do volume/DB | reconstruir a partir do histórico e reprocessar |
| Credencial expira | Média | renovar no servidor e documentar | login manual único no servidor |
| Publicação duplicada | Alta | idempotência por lote + estado persistido | bloquear reenvio do mesmo lote |

---

## 8. Decisões que preciso de você

1. **Onde vai rodar o cron:** no mesmo servidor do Coolify ou em um servidor separado?
2. **Nível de tolerância a falha:** quer só reexecução manual ou retry automático também?
3. **Escopo inicial:** mover só Telegram agora ou Telegram + LinkedIn já no mesmo padrão?

---

## 9. Minha recomendação objetiva

1. **Agora:** mover o Telegram para cron no servidor, dentro do `vagas-php`.
2. **Depois:** adicionar retry, alerta e log estruturado.
3. **Mais tarde:** unificar LinkedIn e demais posts no mesmo padrão operacional.

*Se você quiser, eu já posso transformar isso em um plano de execução de 3 dias com checklist e ordem exata de implementação.*
