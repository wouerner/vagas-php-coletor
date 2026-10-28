# Post de inteligência de mercado PHP — outubro/2026

Destino: r/brdev (Reddit), **postagem manual**. Preparado em 27/10/2026.
Números tirados da base de produção (leitura apenas) — vagas aceitas pelo filtro, publicadas em outubro.

## Antes de postar: pedir autorização à moderação

O r/brdev tem a Regra 9 (proíbe promoção/divulgação). O post é dado, mas tem um link no fim —
então o certo é pedir antes. Texto curto para o modmail:

> Olá! Sou dev e mantenho um coletor de vagas PHP que roda desde 11/10 juntando 13 fontes com filtro
> de curadoria. Separei os números de outubro (222 vagas: nível, modalidade, contrato, stack) e queria
> publicar como levantamento/discussão, não como divulgação — o link aparece uma única vez, como fonte
> dos dados, no fim do texto. Se preferirem, publico sem link nenhum ou coloco o link só em comentário.
> Pode?

## O post

**Título**

Levantei 222 vagas PHP de outubro no Brasil: 6,9 sênior para cada júnior e 98% sem salário

**Corpo**

Contexto: sou dev e montei um coletor que junta vagas PHP de 13 fontes (LinkedIn, portais, ATS) e
descarta o que não é vaga. Ele roda desde 11/10. Separei os números de outubro: 222 vagas publicadas
no mês (abertas agora são 32).

**Nível: o mercado quase não tem porta de entrada**

Das 161 que informam o nível:

- Sênior 81
- Pleno 43
- Especialista 22
- Júnior 13
- Estágio 2

São 103 vagas de alto nível (sênior + especialista) contra 15 de entrada (júnior + estágio): **6,9 para 1**.
Sênior sozinho é metade de tudo. Para quem está começando em PHP, o dado confirma o que todo mundo
comenta no dia a dia.

**Remoto: 57% de quem informa**

97 remotas, 42 presenciais, 30 híbridas — e 24% não informam a modalidade.

**Contrato: PJ 52% x CLT 43%** (das 82 que informam; 63% não informam o regime)

**Salário: 98,2% não informam faixa**

Só 4 das 222 diziam o salário: R$ 3.001–4.000 (júnior), R$ 10.000–12.000 (sênior),
R$ 10.000–120.000 (sênior — parece erro de digitação da empresa) e uma em dólar. Se alguém aqui tem
dado de salário PHP no Brasil melhor do que "pergunta no Glassdoor", é exatamente o que eu queria ver.

**O que pedem junto com PHP** (das 222)

- Laravel 119 (54%)
- JavaScript/TypeScript 111 (50%)
- MySQL 80 · React 77 · API REST 75 · CI/CD 70 · Docker 67 · AWS 54 · PostgreSQL 52 · testes 52 ·
  Vue 46 · Node 43 · Python 41 · Angular 31 · WordPress 26 · Symfony 25 · Kubernetes 25

Laravel aparece 4,8x mais que Symfony. E metade das vagas pede JavaScript junto — PHP "puro"
praticamente não existe mais.

**Onde:** SP 39, RS 15, DF 12, SC 6, RJ 5, MG 5, PR 3, e 63 são remotas/Brasil. Cerca de 24% das vagas
com local informado são de São Paulo.

**Empresas que mais anunciaram em outubro:** Digisystem 11, BairesDev 7, e várias com 2 (EBANX,
Grupo Boticário, Stefanini, ioasys, Viceri SEIDOR, Bun/Buntech, Hitss, Proxify). Foram 109 empresas
diferentes no mês. Jobgether e "BuscarVagas" aparecem com 10 cada, mas são plataformas repostando
vaga, não empregadoras.

**Sobre a curadoria, porque isso muda a leitura**

Nos 17 dias, 11.384 anúncios únicos passaram pelas fontes e 478 viraram vaga no site (4%). Só no
LinkedIn, das 324 publicações analisadas, 267 (82%) foram descartadas: 123 não tinham nada de
contratação, 111 eram listas ou reposts de perfil agregador, 13 eram gente mostrando o projeto do
curso e o resto era outro assunto. Resumindo: quase tudo que aparece como "vaga PHP" em feed é ruído.

**Limites do dado, para não vender ilusão:** são 17 dias de coleta e 222 vagas; 24% não informam
modalidade e 28% não informam nível, então as porcentagens valem sobre quem informa; e 98% não dizem
salário, então não tenho como falar de faixa real do mercado.

Sou eu que mantenho a ferramenta (vagasphp.wouerner.dev). Se falar dela for contra a regra do sub, eu
removo e fica só o dado. Os números saem do que o coletor aceita, e o filtro é público em /regras.

O que mais me chamou atenção foi essa razão sênior/júnior. Quem trabalha com PHP: isso bate com o que
vocês veem nas entrevistas?

## Como medir o retorno (depois de postar)

- GA (property 559268978): sessões com origem `reddit.com` — a referência é o total diário (~28/dia).
- Cliques em `/out` por fonte: já registra o destino, mas ainda conta robô (VBP-010), então serve como
  sinal grosseiro.
- O que interessa de verdade: quantos dos que chegarem entram no canal do Telegram.

## Números de apoio (conferência)

Janela: vagas aceitas (sem repetidas) com publicação a partir de 01/10/2026 — 222 vagas.
Base total: 11.384 itens únicos desde 11/10; 478 aceitos (4,2%); 32 abertas em 27/10.
Volume: ~14,6 vagas novas por dia útil e 3 por dia no fim de semana.
Nível (161 informam): sênior 81, pleno 43, especialista 22, júnior 13, estágio 2.
Modalidade (169 informam): remoto 97, presencial 42, híbrido 30; 53 sem informação.
Contrato (82 informam): PJ 43, CLT 35, freelance 4; 140 sem informação.
Salário: 4 de 222 informam faixa.
Stack (das 222): Laravel 119, JavaScript/TS 111, MySQL 80, React 77, API REST 75, CI/CD 70,
Docker 67, AWS 54, PostgreSQL 52, testes 52, Vue 46, Node 43, Python 41, Angular 31, WordPress 26,
Symfony 25, Kubernetes 25, Redis 28, microsserviços 32, Azure 21, Magento 9, Drupal 9, CodeIgniter 9.
Local (163 informam): remoto/Brasil 63, SP 39, RS 15, DF 12, SC 6, RJ 5, MG 5, PR 3, outros 8.
Empresas: 109 distintas em outubro; Digisystem 11, Jobgether 10 (plataforma), BuscarVagas 10
(plataforma), BairesDev 7.
LinkedIn: 324 publicações analisadas, 57 aceitas, 267 recusadas (no_hiring 123, aggregator 57,
aggregator_author 42, other_subject 14, showcase 13, job_list 12, self_author 4, job_seeker 1).
Fontes (aceitas): programathor 243, linkedin 104, post 57, remotar 16, nerdin 14, github 9, gupy 9,
catho 6, inhire 6, recrutei 5, upvagas 4, solides 3, coodesh 1.

## Achado colateral para o produto (VBP)

**251 das 478 vagas aceitas (53%) têm data de publicação antiga informada pela fonte** — 197 com mais
de um ano, praticamente todas do Programathor (238). O Programathor entrega o catálogo inteiro com a
data original: em 14/10 entraram 274 vagas de uma vez, quase todas antigas.
Isso não suja a home (a vitrine usa janela de 72 h por data de publicação), mas **distorce qualquer
número de mercado** calculado sobre "aceitas" — inclusive as páginas /mercado-php, /dashboard e o
relatório M1 que queremos vender. Por isso esta postagem usa só as 222 com publicação em outubro.
Correção sugerida: nas estatísticas de mercado, filtrar por data de publicação recente (ou usar
first_seen) e marcar as vagas de catálogo antigo.
