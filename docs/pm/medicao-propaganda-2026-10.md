# Medição da propaganda — pausa nos posts do LinkedIn

**PM:** Hermes · **Data:** 27/10/2026 · **Status:** medindo
**Decisão do dono:** pausar o post diário no perfil do LinkedIn, por tempo indeterminado, para medir o efeito do que já foi feito.

---

## 1. O que foi pausado e o que continua

| | Situação |
|---|---|
| Post diário no perfil do LinkedIn (job `b7ba1dfc1fd7`, 9h) | **Pausado em 27/10/2026** (`hermes cron pause b7ba1dfc1fd7`; retomar = `hermes cron resume b7ba1dfc1fd7`) |
| Canal do Telegram (4 alertas/dia + resumo semanal) | Continua rodando |
| Site, coleta, QA diário das 3 primeiras vagas, relatórios | Continua rodando |

## 2. O que a campanha publicou (15–27/10)

- **6 posts publicados** em 13 dias: 15, 22, 24, 25, 26 e 27/10.
- **7 dias sem post**: 16 a 21/10 e 23/10 — o publicador falhou em todos (seletor do editor do LinkedIn; 3 tentativas por dia entre 16 e 21/10).
- O canal do Telegram entrou no ar em **22/10**, no meio da campanha.

## 3. O que o GA mostra (única janela que existe: 15–27/10)

O GA só tem dado a partir de **15/10** — exatamente o dia do primeiro post. **Não existe período anterior à campanha para comparar.** Qualquer número abaixo é "o que entrou", não "quanto a campanha causou".

| Métrica (12 dias: 15–26/10) | Valor |
|---|---|
| Sessões | **333** (média 27,8/dia) |
| Usuários | 191 |
| Usuários novos | 189 |
| Visualizações de página | 913 |
| Sessões do LinkedIn | **140 (42%)** — `linkedin.com` 127 + `lnkd.in` 13 |
| Direct | 193 (58%) — inclui navegador interno do LinkedIn e do Telegram, que não manda referenciador |
| Assistente de IA (`claude.ai`) | 1 |

Dias com mais sessão: 23/10 (97), 22/10 (94), 26/10 (85). Fim de semana rende pouco (24/10: 20; 25/10: 15), mesmo com post publicado.

Páginas mais vistas: home 509, `/empresas` 102, `/dashboard` 40, `/mercado-php` 20, `/regras` 18. As páginas de vaga ficam entre 7 e 10 cada — quem chega do LinkedIn olha a lista, quase não abre vaga individual.

## 4. Nossa própria medição de cliques (instrumento novo)

A tabela `clicks` (link `/out`) só passou a gravar em **23/10, 10:36 UTC** — 943 cliques até agora.

**Atenção: esse número está inflado por robô.** Em 27/10 houve um pico de **155 cliques em uma única hora (05h de Brasília)**, o que não é comportamento humano. O contador não filtra agente nenhum. Antes de usar esse número como métrica, é preciso excluir crawler (o GA é a fonte confiável para audiência; o `/out` serve para comparar cliques *entre* vagas e páginas).

## 5. O experimento que começa agora

**Hipótese:** os posts no perfil eram o principal motor de tráfego; sem eles, as sessões caem de forma visível em uma semana.

**Como medir (toda segunda, 14 dias):**

| Métrica | Onde | Durante a campanha | Leitura |
|---|---|---|---|
| Sessões/dia | GA | 27,8 | cai para ~5 ou se mantém? |
| Sessões do LinkedIn | GA (`sessionSource`) | 140 em 12 dias | deve tender a quase 0 em poucos dias |
| Sessões direct | GA | 193 | proxy do navegador interno (LinkedIn + Telegram) |
| Inscritos no canal | relatório do canal (8h05) | 121 (+9/dia) | o canal segue crescendo sozinho? |
| Cliques/dia em `/out` | base | 943 desde 23/10 | só depois de filtrar robô |

**Regra de decisão em 14 dias (10/11):**
- Se as sessões do LinkedIn forem a quase zero **e** o total cair mais de 60% (abaixo de ~11/dia): os posts eram o motor. Retomar com cadência menor (3x/semana) e medir de novo.
- Se o total se mantiver em 60% ou mais (~17/dia) sem os posts: o canal do Telegram está fazendo o trabalho e o perfil era redundante. Manter pausado.
- Caso intermediário: manter pausado mais 14 dias, porque a série é curta demais para decidir.

## 6. Cuidados para não se enganar

1. **Amostra pequena.** 333 sessões em 12 dias não sustentam conclusão forte; a decisão de 14 dias é uma leitura de tendência, não de significância.
2. **Confusão com o canal.** O Telegram começou em 22/10 e não para. Se o tráfego continuar de pé durante a pausa, é o canal, não o perfil.
3. **Sem linha de base.** O GA nasceu junto com a campanha. Daqui para a frente o dado é limpo; para trás, não existe.
4. **Mudanças feitas no meio da campanha** que também mexem em tráfego: correções de SEO/robots (26/10), WebMCP (26/10), correção de filtros (24 e 25/10) e o dedupe do Telegram. Nada disso é propaganda.
5. **Fim de semana rende pouco** (20 e 15 sessões contra 85–97 em dia útil). Comparar semana com semana, nunca dia com dia.

## 7. Itens que ficam no backlog a partir disto

- **Filtrar robô no contador de cliques** (`/out`): sem isso o número de cliques não serve para decidir nada. Gravado como `VBP-010`.
- **Consertar o publicador do LinkedIn** só volta a importar se decidirmos retomar; hoje ele falha em 7 de 13 dias.
