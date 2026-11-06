# Compactação BairesDev — agrupamento por janela de 12h

**PM:** Hermes · **Data:** 03/11/2026 · **Status:** validado em produção
**Escopo:** reduzir ruído da BairesDev no site sem apagar vagas reais.

## 1. Problema

A BairesDev está publicando muitas vagas PHP em sequência, com títulos parecidos e cidades diferentes. No feed isso parece repetição, infla a lista e piora a leitura.

## 2. Validação em produção

**Produção:** `https://vagasphp.wouerner.dev`

**Evidência viva:** `/api/jobs?limit=200&q=bairesdev&hours=12`

- retornou **16 vagas BairesDev**;
- todas caem numa janela de **3h31m**;
- o maior intervalo entre publicações consecutivas foi de **1h36m**;
- os títulos se repetem em famílias claras:
  - **6** × `Desenvolvedor PHP`
  - **3** × `Senior PHP Developer (Symfony & CodeIgniter)`
  - **2** × `Full Stack Developer (React/PHP)`
  - **1** × `Backend Engineer (PHP)`
  - **1** × `PHP Full-Stack Engineer`
  - **1** × `Semi Senior PHP Developer`
  - **1** × `WordPress Solutions Developer`
- as cidades variam: Curitiba, Guarulhos, Goiânia, Natal, Rio de Janeiro, São Paulo, Minas Gerais e Brasil.

**Leitura de PM:** isso não é só "vaga parecida"; é um burst da mesma empresa. Sem agrupamento, o site mostra volume artificial e cansa o usuário. Com agrupamento, o feed continua honesto, mas legível.

## 3. Regra proposta

Agrupar por empresa quando:

1. a empresa for a mesma (`company_key` / empresa normalizada);
2. as vagas estiverem em sequência temporal com diferença de **até 12 horas** entre publicações consecutivas;
3. cidade, título e stack podem variar sem quebrar o grupo.

**Importante:**
- não apagar vagas da base;
- não juntar empresas diferentes;
- não tratar cidade diferente como vaga nova se a empresa e a janela já formam o mesmo cluster;
- se houver uma nova onda da mesma empresa depois de mais de 12h, abrir novo grupo.

## 4. UX recomendada

Na home e nas páginas de listagem:

- mostrar **1 card por cluster**;
- exibir:
  - empresa;
  - total de vagas no cluster;
  - janela de publicação;
  - resumo dos títulos/cidades;
- permitir expandir para ver as vagas individuais;
- manter a rota/API crua disponível para quem precisar do detalhe completo.

## 5. Critérios de aceite

- A amostra da BairesDev vira **1 cluster** com **16 vagas**.
- Duas ondas da mesma empresa separadas por mais de 12h viram **2 clusters**.
- Busca, filtros e ordenação continuam funcionando.
- Vagas encerradas/dismissed continuam fora, como hoje.
- O número total da base não muda; muda só a apresentação.
- A listagem agrupada não quebra o acesso às vagas filhas.

## 6. Riscos / decisões

- Definir se o agrupamento entra por padrão na home ou só em uma flag de query.
- Definir se o card mostra a vaga mais recente como líder do grupo ou um resumo neutro.
- Garantir que o agrupamento não esconda uma vaga real com descrição diferente dentro da mesma empresa.

## 7. Backlog

- `VBP-012` — Compactar vagas da mesma empresa em janela de 12h.
- Status: pronto para implementação.
