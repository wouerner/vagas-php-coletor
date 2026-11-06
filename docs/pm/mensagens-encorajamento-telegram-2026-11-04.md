# Vagas PHP — mensagens curtas de encorajamento no Telegram

**PM:** Hermes · **Data:** 04/11/2026 · **Status:** v1
**Objetivo:** reduzir a sensação de abandono para quem está há semanas ou meses procurando emprego, sem transformar o canal em autoajuda nem aumentar o ruído.

---

## 1. Problema

Quem recebe vaga todo dia também recebe silêncio, rejeição e cansaço. Se o canal só despeja lista, ele informa; não sustenta.

O ponto aqui não é “animar por animar”. É fazer a pessoa continuar abrindo o canal sem sentir que está ficando para trás.

---

## 2. Princípios de conteúdo

1. **Curto:** 1 frase, no máximo 2.
2. **Concreto:** sempre ligado ao ato de procurar vaga, aplicar ou seguir.
3. **Sem promessa falsa:** nada de “vai dar certo”, “só depende de você”, “não desista” genérico.
4. **Sem culpa:** não tratar a busca longa como falha moral.
5. **Sem excesso de emoji:** no máximo 1, e só se não soar infantil.
6. **Não virar postagem separada:** a mensagem entra junto do alerta ou do resumo, não como feed motivacional.

---

## 3. Onde usar

### P0 — no final dos alertas do Telegram
- Uma linha curta no rodapé do envio.
- Serve para humanizar a lista sem competir com as vagas.
- Melhor posição: depois da lista ou antes do link final.

### P1 — no resumo semanal
- Uma frase mais cuidadosa, porque o resumo já é menos urgente.
- Funciona bem para lembrar que o esforço acumulado conta.

### P2 — em situações de maior frustração
- Quando o canal estiver com menos vagas ou o mercado estiver fraco, a frase pode reconhecer o contexto.
- Ex.: “Hoje tem menos coisa boa — e tudo bem. Segue filtrando com calma.”

---

## 4. Biblioteca de mensagens

### Tom de normalização
- “Buscar emprego por meses não é atraso; é processo.”
- “Você não está parado — está filtrando melhor.”
- “Uma vaga boa por vez já é progresso.”

### Tom de continuidade
- “Se hoje não foi, amanhã a triagem continua.”
- “Continuar aplicando ainda é estratégia.”
- “Constância ganha de ansiedade.”

### Tom de alívio
- “Respira: ler, escolher e aplicar já é trabalho.”
- “Nem todo dia vai render resposta; o importante é manter o ritmo.”
- “Você não precisa vencer o mercado hoje. Precisa seguir nele.”

### Tom de cuidado com busca longa
- “Se a busca já está longa, isso não define seu valor.”
- “Meses procurando não apagam sua experiência.”
- “A vaga certa costuma demorar mais do que a gente queria.”

---

## 5. Regra editorial

Cada mensagem precisa cumprir esta fórmula:

**reconhece o cansaço + reforça continuidade + não promete resultado**

Exemplo:
- “Buscar há meses cansa. Ainda assim, cada aplicação boa conta.”

Se faltar uma dessas três partes, corta.

---

## 6. Implementação sugerida

### V1
- Criar um conjunto fixo de 12 frases.
- Rotacionar 1 frase por envio do Telegram.
- Manter a frase curta e sempre no mesmo ponto do template.

### V2
- Separar por contexto:
  - alerta normal
  - alerta fraco
  - resumo semanal
- Cada contexto com 4 frases próprias.

### V3
- Testar se a frase deve aparecer sempre ou só em parte dos envios.
- Se houver queda de clique ou de retenção, remover primeiro a frase antes de mexer no resto do conteúdo.

---

## 7. Métricas

| Métrica | Como medir | Sinal de sucesso |
|---|---|---|
| Views por post | views públicas do canal | não cair após inserir a frase |
| Cliques no link | `/out` | manter ou subir |
| Crescimento de inscritos | `getChatMembersCount` | não piorar após a mudança |
| Reação qualitativa | respostas/referências diretas | comentários do tipo “isso ajudou” |

**Regra:** se a frase reduzir clareza ou parecer forçada, volta para o texto puro.

---

## 8. Riscos

| Risco | Sintoma | Plano B |
|---|---|---|
| Virar “coach” | mensagem soa artificial | cortar a frase e deixar só as vagas |
| Repetição cansativa | mesma linha aparece demais | rotacionar a biblioteca e limitar frequência |
| Poluir o feed | comentário longo demais | manter em 1 linha, sem parágrafo extra |
| Falsa expectativa | promessa implícita de resultado | remover qualquer frase de garantia |

---

## 9. Backlog

| ID | Prioridade | Esforço | Item | Aceitação |
|---|---|---|---|---|
| VAG-ENC-001 | P0 | S | Criar biblioteca inicial de 12 mensagens | frases curtas, humanas e sem promessa falsa |
| VAG-ENC-002 | P0 | S | Inserir mensagem rotativa no Telegram alert | cada envio escolhe 1 frase da biblioteca |
| VAG-ENC-003 | P1 | S | Adicionar versão específica para o resumo semanal | o resumo tem um tom menos urgente e mais encorajador |
| VAG-ENC-004 | P1 | S | Medir efeito por 2 semanas | comparar views, cliques e crescimento antes/depois |

---

## 10. Decisões que você precisa tomar

1. A mensagem entra **sempre** no alerta ou só em alguns envios?
2. O tom deve ser mais **direto** ou mais **acolhedor**?
3. Quer que eu siga com a implementação já no template do Telegram?
