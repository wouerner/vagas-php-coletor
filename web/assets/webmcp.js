// Ferramentas de leitura para agentes de IA (WebMCP, rascunho do W3C de 20/10/2026:
// https://webmachinelearning.github.io/webmcp/). Servido em /webmcp.js e incluído por
// seo.render() fora de ?print=1. Sem WebMCP no navegador, não faz nada.
// O rascunho do W3C só descreve a API imperativa, mas o Chrome (origin trial a partir do
// 149) tem DUAS APIs, e as duas valem aqui:
// - Imperativa: document.modelContext.registerTool({name, title, description,
//   inputSchema (objeto), execute, annotations}), usada abaixo.
// - Declarativa: atributos toolname/tooldescription no <form>. EXISTE: o <form id="filters">
//   da home é anotado com toolname="buscar_vagas". Não remova.
//   Fontes: doc WebMCP do Chrome, seção "Use WebMCP APIs" (atualizada em 07/10/2026):
//   "There are two APIs… Imperative API… Declarative API: Add annotations to a standard
//   HTML forms to create a WebMCP tool."; doc do Lighthouse "Registered WebMCP tools"
//   (atualizada em 21/09/2026): "Declarative API: Add `toolname` and `tooldescription`
//   attributes directly to your `<form>` elements."
// O que NÃO existe é SubmitEvent.agentInvoked/respondWith: nada de listener de submit.
// As 4 ferramentas são registradas em toda página, home inclusive. Na home, buscar_vagas
// coincide com a ferramenta declarativa do formulário; o nome é único por página, então o
// Chrome rejeita o registerTool duplicado e o .catch(() => {}) engole a rejeição. Isso é
// esperado, não é erro: a busca fica com a versão declarativa e as outras 3 seguem
// imperativas. Nas demais páginas, as 4 são imperativas.
// Cada ferramenta lê a API do próprio site (mesma origem) e devolve JSON enxuto: o agente
// paga por token. Nenhuma escreve nada.
(() => {
  const doc = typeof document !== "undefined" ? document : undefined;
  const ctx = (doc && doc.modelContext) ||
    (typeof navigator !== "undefined" && navigator && navigator.modelContext) || null;
  if (!ctx || typeof ctx.registerTool !== "function") return;

  const SITE = location.origin;  // o próprio site (forks não apontam para o original)
  const WORKPLACES = ["Remoto", "Híbrido", "Presencial"];
  const SENIORITIES = ["Estágio", "Júnior", "Pleno", "Sênior", "Especialista"];
  const STACKS = ["Laravel", "Symfony", "CodeIgniter", "CakePHP", "Yii", "Laminas/Zend",
    "Hyperf/Swoole", "Livewire", "Filament", "Magento", "WordPress", "Drupal"];

  const getJSON = async path => {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };
  // Erro vira resposta legível, não exceção: o agente entende e segue.
  const safe = fn => async (input, client) => {
    try { return await fn(input || {}, client); }
    catch (e) { return { error: `Não foi possível consultar o Vagas PHP agora (${e && e.message || e}). Tente de novo em instantes.` }; }
  };
  const clamp = (n, def, min, max) => {
    n = Math.round(Number(n));
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : def;
  };
  // Tira campos vazios: menos tokens.
  const compact = o => Object.fromEntries(Object.entries(o).filter(([, v]) =>
    v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length)));
  const top = (pairs, n) => (pairs || []).filter(([, c]) => c > 0).slice(0, n);

  const jobsQuery = input => {
    const p = new URLSearchParams({ limit: "10" });
    for (const k of ["q", "stack", "workplace", "seniority", "source"]) {
      const v = input[k] == null ? "" : String(input[k]).trim();
      if (v) p.set(k, v);
    }
    if (input.hours != null) p.set("hours", String(clamp(input.hours, 72, 1, 72)));
    return p;
  };
  const searchJobs = async input => {
    const p = jobsQuery(input);
    const data = await getJSON("/api/jobs?" + p);
    p.delete("limit");
    return {
      page: SITE + "/" + (p.toString() ? "?" + p : ""),
      jobs: (data.jobs || []).map(j => compact({
        seq: j.seq, title: j.title,
        [j.source === "post" ? "author" : "company"]: j.source === "post" ? j.author : j.company,
        workplace: j.workplace, seniority: j.seniority,
        stack: j.stack ? String(j.stack).split(",") : null,
        url: j.url, site: j.path ? SITE + j.path : null,
      })),
      has_more: !!data.has_more,
    };
  };

  const tools = [
    {
      name: "buscar_vagas",
      title: "Buscar vagas PHP",
      description: "Busca vagas abertas de desenvolvimento PHP (últimas 72 h) coletadas de portais " +
        "e publicações do LinkedIn. Filtra por texto livre, stack, modalidade, senioridade e " +
        "período. Devolve até 10 vagas com link do anúncio original e da página no site.",
      inputSchema: {
        type: "object",
        properties: {
          q: { type: "string", description: "Texto livre: cargo, empresa ou tecnologia." },
          stack: { type: "string", enum: STACKS, description: "Framework ou plataforma PHP." },
          workplace: { type: "string", enum: WORKPLACES, description: "Modalidade de trabalho." },
          seniority: { type: "string", enum: SENIORITIES, description: "Senioridade." },
          hours: { type: "integer", minimum: 1, maximum: 72, description: "Só vagas publicadas nas últimas N horas (padrão 72)." },
        },
        additionalProperties: false,
      },
      // Título, empresa e autor vêm de anúncios coletados de terceiros ("Output Injection
      // Attacks" no rascunho): o agente não deve tratar esse texto como instrução.
      annotations: { readOnlyHint: true, untrustedContentHint: true },
      execute: safe(searchJobs),
    },
    {
      name: "estatisticas_mercado",
      title: "Estatísticas do mercado PHP",
      description: "Números do mercado de vagas PHP: vagas abertas, novas em 24 h, remotas, " +
        "empresas, e cortes por fonte, por dia, modalidade, senioridade, stack e empresa.",
      inputSchema: {
        type: "object",
        properties: {
          days: { type: "integer", minimum: 3, maximum: 90, description: "Dias da série diária (padrão 14)." },
        },
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute: safe(async input => {
        const days = clamp(input.days, 14, 3, 90);
        const d = await getJSON("/api/dashboard?days=" + days);
        if (d.error) throw new Error(d.error);
        return {
          page: SITE + "/dashboard",
          open_window_hours: d.max_age_hours,
          kpis: d.kpis,
          by_source: top(d.by_source, 20),
          daily: (d.daily || []).map(({ day, ...bySource }) =>
            [day, Object.values(bySource).reduce((a, b) => a + (Number(b) || 0), 0)]),
          workplace: top(d.workplace, 5),
          seniority: top(d.seniority, 6),
          stack: top(d.stack, 8),
          companies: top(d.companies, 5),
        };
      }),
    },
    {
      name: "regras_de_curadoria",
      title: "Regras de curadoria",
      description: "Regras que decidem quais vagas e publicações entram ou ficam de fora do " +
        "Vagas PHP (efeito: aceita ou recusa), com quantas vagas cada regra já decidiu.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true },
      execute: safe(async () => {
        const d = await getJSON("/api/rules");
        const counts = d.counts || {};
        return {
          page: SITE + "/regras",
          rules: (d.rules || []).map(r => compact({
            id: r.id, group: r.group, title: r.title, effect: r.effect, decided: counts[r.id],
          })),
        };
      }),
    },
    {
      name: "empresas_que_contratam",
      title: "Empresas que contratam PHP",
      description: "Empresas que mais anunciaram vagas PHP em portais nos últimos 90 dias, " +
        "com o número de vagas e a stack pedida.",
      inputSchema: {
        type: "object",
        properties: {
          limit: { type: "integer", minimum: 1, maximum: 50, description: "Quantas empresas (padrão 10)." },
        },
        additionalProperties: false,
      },
      // Nomes de empresa vêm dos anúncios coletados: conteúdo de terceiros.
      annotations: { readOnlyHint: true, untrustedContentHint: true },
      execute: safe(async input => {
        const d = await getJSON("/api/companies");
        return {
          page: SITE + "/empresas",
          days: d.days,
          companies: (d.companies || []).slice(0, clamp(input.limit, 10, 1, 50))
            .map(c => compact({ name: c.name, jobs: c.jobs, stack: c.stack })),
        };
      }),
    },
  ];

  for (const tool of tools) {
    try {
      Promise.resolve(ctx.registerTool(tool)).catch(() => {});
    } catch (e) { /* navegador recusou a ferramenta: o site segue igual */ }
  }
})();
