<?php

declare(strict_types=1);

namespace VagasPhp;

use PDOException;
use VagasPhp\Http\Request;
use VagasPhp\Http\Response;
use VagasPhp\Http\Router;

/**
 * Site que lista as vagas PHP coletadas. Lê a base do coletor (MySQL); só grava os cliques.
 *
 * Rotas: /             página (templates/index.html), com as primeiras vagas já no HTML
 *        /api/jobs     vagas em JSON (filtros: q, source, workplace, seniority, stack, hours,
 *                      include_closed, limit, offset); `path` é a página da vaga no site
 *        /api/stats    totais por fonte, vagas abertas (open_total) e últimas coletas
 *        /vagas        temas (stack, modalidade, senioridade e combinações) com contagem
 *        /vagas/<tema> vagas abertas de um tema (templates/tema.html), ex.: /vagas/laravel-remoto
 *        /dashboard    dashboard; /api/dashboard: números (days: dias da série diária, 3-90)
 *        /regras       regras de filtro; /api/rules: as regras, quantas vagas cada uma decidiu
 *                      e as descartadas à mão
 *        /recrutadores tech recruiters que mais publicam vagas PHP; /api/recruiters: a lista
 *                      (últimos 90 dias, VAGAS_RECRUITERS_MIN vagas ou mais, sem os perfis de
 *                      VAGAS_RECRUITERS_HIDE)
 *        /empresas     empresas que mais anunciam vagas PHP; /api/companies: a lista
 *        /contato      como falar com quem mantém o site
 *        /sitemap.xml, /robots.txt, /og.png, /webmcp.js
 *        /mercado-php  números do mercado PHP em texto (Mercado), e /llms.txt
 *        /vaga/<seq>-<título>  página de uma vaga de portal, com JobPosting (Vaga)
 *        /out          conta o clique (tabela clicks) e redireciona para o anúncio original
 *        /api/clicks   cliques dos últimos `days` dias (padrão 7)
 *
 * Google Analytics: com VAGAS_GA_ID=G-XXXXXXXXXX as páginas recebem a tag
 * (templates/analytics.html). ?print=1 tira a tag (print do dashboard para o post diário).
 */
final class Site
{
    public const SOURCE_NAMES = ['linkedin' => 'Vaga LinkedIn', 'gupy' => 'Gupy', 'post' => 'Publicação LinkedIn',
        'github' => 'GitHub', 'inhire' => 'InHire', 'solides' => 'Sólides', 'catho' => 'Catho',
        'remotar' => 'Remotar', 'programathor' => 'Programathor', 'coodesh' => 'Coodesh',
        'nerdin' => 'Nerdin', 'recrutei' => 'Recrutei', 'upvagas' => 'UpVagas'];
    /** Idade da vaga: até quantas horas, classe do card e nome da faixa. */
    public const AGE_BANDS = [[6, 'new', 'nova'], [24, 'recent', 'recente'], [48, 'days', '1-2 dias'],
        [INF, 'old', 'antiga']];
    /** Explicação do número de cliques do card (o mesmo CLICKS_TIP do JavaScript). */
    public const CLICKS_TIP = 'Quantas vezes alguém abriu o anúncio original a partir do Vagas PHP desde que '
        . 'a vaga entrou no site. Dá uma noção da concorrência, mas não inclui quem viu a vaga direto '
        . 'na fonte (LinkedIn, Gupy...), e a mesma pessoa pode contar mais de uma vez.';
    /**
     * Cabeçalhos de segurança de toda resposta (quem responde pode trocar). A CSP aceita os
     * <script> e <style> inline dos templates e só o Google Analytics de fora; nada embute o
     * site em iframe.
     */
    public const SECURITY_HEADERS = [
        'Strict-Transport-Security' => 'max-age=31536000',
        'X-Content-Type-Options' => 'nosniff',
        'X-Frame-Options' => 'DENY',
        'Referrer-Policy' => 'strict-origin-when-cross-origin',
        'Content-Security-Policy' => "default-src 'self'; "
            . "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; "
            . "style-src 'self' 'unsafe-inline'; "
            . "img-src 'self' data: https://*.google-analytics.com https://*.googletagmanager.com; "
            . "connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com "
            . 'https://*.googletagmanager.com; '
            . "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    ];
    public const PAGE = 30;  // vagas na primeira página da home (o mesmo PAGE do JavaScript)
    public const RECRUITERS_DAYS = 90;
    public const COMPANIES_DAYS = 90;
    public const COMPANIES_MIN = 2;
    public const PAGES = ['/', '/vagas', '/dashboard', '/empresas', '/recrutadores', '/regras', '/mercado-php', '/contato'];
    /** Grupos da página /regras: id nas regras do filtro, título e explicação. */
    public const RULE_GROUPS = [
        ['vagas', 'Vagas de portais', 'LinkedIn Vagas, Gupy, Sólides, Catho, Remotar, Programathor, '
            . 'Coodesh, Nerdin, Recrutei, UpVagas, páginas de carreira de empresas na InHire e issues dos '
            . 'repositórios de vagas no GitHub.'],
        ['posts', 'Publicações do LinkedIn', 'Posts que anunciam vagas. Precisam falar de PHP, '
            . 'anunciar uma vaga e não ser outra coisa.'],
        ['empresas', 'Empresas', 'Quem aparece na página de empresas, entre as vagas de portais aceitas.'],
        ['recrutadores', 'Recrutadores', 'Quem aparece na página de recrutadores, entre os autores das '
            . 'publicações aceitas.'],
    ];

    private ?Themes $themes = null;
    private ?array $openJobs = null;

    public function __construct(public readonly Repo $repo, private readonly string $assets)
    {
    }

    public static function recruitersMin(): int
    {
        return max((int) (getenv('VAGAS_RECRUITERS_MIN') ?: 2), 1);
    }

    /** @return list<string> */
    public static function recruitersHide(): array
    {
        return array_values(array_filter(array_map('trim', explode(',', (string) getenv('VAGAS_RECRUITERS_HIDE')))));
    }

    public function router(): Router
    {
        $r = new Router();
        $r->get('/', $this->index(...));
        $r->get('/api/jobs', $this->jobs(...));
        $r->get('/api/stats', $this->stats(...));
        $r->get('/vagas', $this->themesPage(...));
        $r->get('/vagas/{slug}', $this->themePage(...));
        $r->get('/dashboard', $this->dashboardPage(...));
        $r->get('/api/dashboard', $this->dashboard(...));
        $r->get('/regras', $this->rulesPage(...));
        $r->get('/api/rules', $this->rules(...));
        $r->get('/recrutadores', $this->recruitersPage(...));
        $r->get('/api/recruiters', $this->recruiters(...));
        $r->get('/empresas', $this->companiesPage(...));
        $r->get('/api/companies', $this->companies(...));
        $r->get('/contato', $this->contatoPage(...));
        $r->get('/sitemap.xml', $this->sitemap(...));
        $r->get('/robots.txt', $this->robots(...));
        $r->get('/og.png', fn () => $this->asset('og.png', 'image/png'));
        $r->get('/webmcp.js', fn () => $this->asset('webmcp.js', 'application/javascript'));
        $r->get('/out', $this->out(...));
        $r->get('/api/clicks', $this->clicks(...));
        $mercado = new Mercado($this);
        $r->get(Mercado::PATH, $mercado->page(...));
        $r->get('/llms.txt', $mercado->llmsTxt(...));
        $r->get('/vaga/{ref}', (new Vaga($this))->page(...));
        return $r;
    }

    /**
     * Toda resposta leva SECURITY_HEADERS. Respostas /api/* levam X-Robots-Tag: noindex: o
     * Googlebot busca mas não indexa o JSON.
     */
    public function handle(Request $request): Response
    {
        $response = $this->router()->dispatch($request);
        if (str_starts_with($request->path, '/api/')) {
            $response->headers += ['X-Robots-Tag' => 'noindex'];
        }
        $response->headers += self::SECURITY_HEADERS;
        return $response;
    }

    /**
     * Roda `fn`; se as tabelas ainda não existem (o coletor não rodou), devolve `default`.
     *
     * @template T
     * @param callable(): T $fn
     * @param T $default
     * @return T
     */
    public static function safe(callable $fn, mixed $default): mixed
    {
        try {
            return $fn();
        } catch (PDOException $e) {
            if (Db::isMissingTable($e)) {
                return $default;
            }
            throw $e;
        }
    }

    public function themes(): Themes
    {
        return $this->themes ??= new Themes($this->repo->meta('taxonomy'));
    }

    public static function number(?string $value, float $default, float $low, float $high): float
    {
        return is_numeric($value) ? min(max((float) $value, $low), $high) : $default;
    }

    // --- cards de vaga renderizados no servidor ----------------------------------------
    // Mesmo HTML que card() de templates/index.html monta no navegador: o JavaScript troca a
    // lista inicial pela dele sem mudar nada na tela. Mudou um, mude o outro.

    /** Texto curto ("40 min", "5 h", "1 d 3 h"), faixa de cor e data em Brasília. */
    public static function age(?string $iso): ?array
    {
        if (!($when = Dates::parse($iso))) {
            return null;
        }
        $minutes = max(0, intdiv(Dates::secondsSince($when), 60));
        $h = $minutes / 60;
        if ($minutes < 60) {
            $text = "$minutes min";
        } elseif ($h < 24) {
            $text = (int) $h . ' h';
        } else {
            $text = intdiv((int) $h, 24) . ' d' . (((int) $h % 24) ? ' ' . ((int) $h % 24) . ' h' : '');
        }
        foreach (self::AGE_BANDS as [$limit, $band, $label]) {
            if ($h < $limit) {
                break;
            }
        }
        return ['text' => $text, 'band' => $band, 'label' => $label,
            'at' => Dates::local($when)->format('d/m, H:i')];
    }

    public static function ago(?string $iso): ?string
    {
        if (!($when = Dates::parse($iso))) {
            return null;
        }
        $h = intdiv(Dates::secondsSince($when), 3600);
        return $h < 1 ? 'há menos de 1 h' : ($h < 48 ? "há $h h" : 'há ' . intdiv($h, 24) . ' dias');
    }

    /** Link para o anúncio original passando por /out, que conta o clique (outHref() do JS). */
    public static function outHref(string $url, array $job, ?string $page): string
    {
        return '/out?' . Text::query(['url' => $url, 'job' => $job['id'] ?? '', 'page' => $page ?: '/',
            'source' => $job['source'] ?? '']);
    }

    /**
     * Cliques no anúncio original (Repo::withClicks), com a explicação num tooltip que abre
     * no hover e no foco (toque no celular). clicksBadge() de templates/index.html monta o mesmo.
     */
    public static function clicksHtml(int $n): string
    {
        $label = $n === 0 ? 'nenhum clique ainda' : Text::plural($n, 'clique', 'cliques');
        return "<span class=\"clicks\" tabindex=\"0\">$label<span class=\"tip\" role=\"tooltip\">"
            . self::CLICKS_TIP . '</span></span>';
    }

    /** Acrescenta `path`, a página da vaga no site (null para posts do LinkedIn). */
    public static function withPath(array $rows): array
    {
        return array_map(fn ($r) => $r + ['path' => Seo::jobPath($r)], $rows);
    }

    /** `page`: caminho da página que mostra o card, gravado no clique (/out). */
    public static function jobCard(array $job, string $page = '/'): string
    {
        $e = Text::e(...);
        $url = Text::safeUrl($job['url'] ?? null);
        $path = $job['path'] ?? null;
        $out = $url ? self::outHref($url, $job, $page) : null;
        $title = $e($job['title'] ?: '(sem título)');
        $who = implode(' · ', array_filter([$job['company'] ?? null,
            ($job['source'] ?? null) === 'post' ? ($job['author'] ?? null) : null, $job['location'] ?? null]));
        $a = self::age($job['posted_at'] ?: $job['first_seen']);
        $tags = ['<span class="tag src">' . $e(self::SOURCE_NAMES[$job['source']] ?? $job['source']) . '</span>'];
        if (!empty($job['closed_at'])) {
            $tags[] = '<span class="tag closed">encerrada</span>';
        }
        if (!empty($job['workplace'])) {
            $remote = $job['workplace'] === 'Remoto' ? ' remote' : '';
            $tags[] = "<span class=\"tag$remote\">" . $e($job['workplace']) . '</span>';
        }
        foreach ([$job['seniority'] ?? null, $job['contract'] ?? null, $job['salary'] ?? null,
                     ...explode(',', $job['stack'] ?? '')] as $t) {
            if ($t) {
                $tags[] = '<span class="tag">' . $e($t) . '</span>';
            }
        }
        if ($url && isset($job['clicks'])) {  // sem anúncio original não há o que clicar
            $tags[] = self::clicksHtml((int) $job['clicks']);
        }
        // Vaga de portal: o título leva à página da vaga no site e o anúncio original fica
        // na linha de baixo. Post do LinkedIn: o título leva ao post.
        if ($path) {
            $link = '<a class="page" href="' . $e($path) . "\">$title</a>";
        } elseif ($url) {
            $link = '<a href="' . $e($out) . "\" target=\"_blank\" rel=\"noopener\">$title</a>";
        } else {
            $link = $title;
        }
        $meta = $e($who);
        if ($a) {  // some no celular, onde o selo de idade basta
            $meta .= '<span class="when">' . ($who !== '' ? ' · ' : '') . 'publicada em ' . $e($a['at']) . ' (Brasília)</span>';
        }
        if ($path && $url) {
            $meta .= ($meta !== '' ? ' · ' : '') . '<a href="' . $e($out) . '" target="_blank" rel="noopener">ver anúncio original</a>';
        }
        $age = $a ? "<span class=\"age\" title=\"Vaga {$a['label']}: publicada há {$a['text']}\">{$a['text']}</span>" : '';
        $desc = !empty($job['description'])
            ? '<details><summary>Descrição</summary><div class="desc">' . $e($job['description']) . '</div></details>' : '';
        $band = $a ? " {$a['band']}" : '';
        return "<li class=\"job$band\" data-id=\"" . $e($job['id']) . "\"><div class=\"head\"><h2>$link</h2>"
            . "$age</div><div class=\"meta\">$meta</div><div class=\"tags\">" . implode('', $tags) . "</div>$desc</li>";
    }

    /** Todas as vagas abertas (sem repetidas), com `path`. */
    public function openJobs(): array
    {
        return $this->openJobs ??= self::safe(fn () => self::withPath($this->repo->queryJobs(limit: 1000)), []);
    }

    /** JSON-LD ItemList das vagas de uma página (página da vaga no site, ou o post). */
    public function jobList(Request $request, string $name, array $jobs): array
    {
        $base = Seo::siteUrl($request);
        $items = [];
        foreach (array_values($jobs) as $i => $j) {
            $items[] = ['@type' => 'ListItem', 'position' => $i + 1,
                'url' => $j['path'] ? $base . $j['path'] : Text::safeUrl($j['url'] ?? null),
                'name' => $j['title'] ?: '(sem título)'];
        }
        return ['@context' => 'https://schema.org', '@type' => 'ItemList', 'name' => $name,
            'numberOfItems' => count($jobs), 'itemListElement' => $items];
    }

    // --- páginas por tema ----------------------------------------------------------------

    /** Empresas com mais vagas, agrupadas como em /empresas (company_key); GitHub fica de fora. */
    private static function topCompanies(array $jobs, int $n = 5): array
    {
        $names = $count = [];
        foreach ($jobs as $j) {
            if ($j['source'] !== 'github' && ($key = $j['company_key'] ?? null)) {
                $names[$key] ??= trim($j['company']);
                $count[$key] = ($count[$key] ?? 0) + 1;
            }
        }
        return array_map(fn ($p) => [$names[$p[0]], $p[1]], Text::topPairs($count, $n));
    }

    /** Parágrafos da página (HTML) e a meta description, com os números atuais. */
    private static function themeIntro(array $theme, array $jobs, int $last90): array
    {
        $name = Text::lcfirst($theme['name']);
        $tech = $theme['stack'] ?: 'PHP';
        $hours = (int) Dates::maxAgeHours();
        $about = 'Vagas de engenharia de software com ' . Text::e($tech) . ' coletadas do LinkedIn, Gupy, '
            . 'Sólides, Catho, Remotar, Programathor, Coodesh e de outros sites de vagas, além '
            . 'de publicações de recrutadores. A lista é atualizada várias vezes por dia.';
        $history = $last90 ? 'Nos últimos 90 dias o site recebeu ' . Text::plural($last90, 'vaga', 'vagas') . ' deste tema.' : '';
        if (!$jobs) {
            $text = '<p>Não há ' . Text::e($name) . " abertas agora (publicadas nas últimas $hours horas). "
                . "$history Veja os temas relacionados abaixo ou "
                . "<a href=\"/\">todas as vagas PHP</a>.</p><p>$about</p>";
            $desc = "{$theme['name']}: nenhuma aberta nas últimas $hours h. "
                . ($last90 ? "$last90 nos últimos 90 dias. " : '')
                . 'Veja vagas PHP relacionadas, atualizadas várias vezes por dia.';
            return [$text, $desc];
        }
        $n = count($jobs);
        $facts = ['<b>' . Text::plural($n, 'vaga aberta', 'vagas abertas') . "</b>, publicadas nas últimas $hours horas."];
        $remote = count(array_filter($jobs, fn ($j) => ($j['workplace'] ?? null) === 'Remoto'));
        if (!$theme['workplace']) {
            $facts[] = Text::round(100 * $remote / $n) . "% são remotas ($remote de $n).";
        }
        $rest = fn (array $pairs) => $n - array_sum(array_column($pairs, 1));
        $tail = fn (int $r) => $r ? '; ' . Text::plural($r, 'não informa', 'não informam') . '.' : '.';
        $contracts = Text::mostCommon(array_filter(array_map(fn ($j) => $j['contract'] ?? null, $jobs)));
        if ($contracts) {
            $facts[] = 'Contratação: ' . Text::joinAnd(array_map(fn ($p) => "{$p[0]} ({$p[1]})", $contracts)) . $tail($rest($contracts));
        }
        if (!$theme['seniority']) {
            $levels = Text::mostCommon(array_filter(array_map(fn ($j) => $j['seniority'] ?? null, $jobs)));
            if ($levels) {
                $facts[] = 'Senioridade: ' . Text::joinAnd(array_map(fn ($p) => mb_strtolower($p[0]) . " ({$p[1]})", $levels)) . $tail($rest($levels));
            }
        }
        $companies = self::topCompanies($jobs);
        if ($companies) {
            $facts[] = 'Empresas que mais anunciam: '
                . Text::joinAnd(array_map(fn ($p) => Text::e($p[1] > 1 ? "{$p[0]} ({$p[1]})" : $p[0]), $companies)) . '.';
        }
        $text = '<p>' . implode(' ', $facts) . " $history</p><p>$about</p>";
        $desc = $n > 1 ? "$n $name abertas, publicadas nas últimas $hours h"
            : "{$theme['name']}: 1 aberta, publicada nas últimas $hours h";
        if (!$theme['workplace']) {
            $desc .= ', ' . Text::round(100 * $remote / $n) . '% remotas';
        }
        if ($companies) {
            $desc .= '. Empresas: ' . Text::joinAnd(array_column(array_slice($companies, 0, 3), 0));
        }
        return [$text, $desc . '. Atualizado várias vezes por dia.'];
    }

    private function themeHtml(Request $request, string $title, string $description, string $path, string $h1,
                               string $crumb, string $intro, array $jobs, string $more, string $related,
                               ?array $jsonld = null, bool $noindex = false, int $status = 200): Response
    {
        $content = ['h1' => Text::e($h1), 'crumb' => $crumb, 'intro' => $intro,
            'list' => implode('', array_map(fn ($j) => self::jobCard($j, $path), $this->repo->withClicks($jobs))), 'more' => $more,
            'related' => $related];
        return Response::html(Seo::render($request, 'tema.html', $title, $description, $path, $content, $jsonld, $noindex), $status);
    }

    public function themesPage(Request $request): Response
    {
        $jobs = $this->openJobs();
        $themes = $this->themes();
        $counts = $themes->counts($jobs);
        $title = 'Vagas PHP por tema: Laravel, Symfony, WordPress, remotas, júnior e sênior | Vagas PHP';
        $description = count($jobs) . ' vagas PHP abertas agora, separadas por stack (Laravel, Symfony, '
            . 'WordPress, Magento...), modalidade (remoto, híbrido, presencial) e senioridade.';
        $base = Seo::siteUrl($request);
        $items = [];
        foreach (array_values($themes->themes) as $i => $t) {
            $items[] = ['@type' => 'ListItem', 'position' => $i + 1, 'url' => $base . $t['path'], 'name' => $t['name']];
        }
        $jsonld = [Seo::breadcrumbs($request, ['Vagas PHP', '/'], ['Temas', '/vagas']),
            ['@context' => 'https://schema.org', '@type' => 'ItemList', 'name' => 'Vagas PHP por tema',
                'itemListElement' => $items]];
        $intro = '<p>As <b>' . Text::plural(count($jobs), 'vaga aberta', 'vagas abertas') . '</b> do site '
            . '(publicadas nas últimas ' . (int) Dates::maxAgeHours() . ' horas), separadas por tema. '
            . 'O número ao lado de cada tema é quantas estão abertas agora.</p>';
        return $this->themeHtml($request, $title, $description, '/vagas', 'Vagas PHP por tema', 'Temas', $intro,
            [], '', $themes->allHtml($counts), $jsonld);
    }

    public function themePage(Request $request): Response
    {
        $slug = $request->params['slug'];
        $themes = $this->themes();
        if (isset($themes->aliases[$slug])) {
            return Response::redirect("/vagas/{$themes->aliases[$slug]}", 301);
        }
        $jobs = $this->openJobs();
        $counts = $themes->counts($jobs);
        if (!($theme = $themes->themes[$slug] ?? null)) {
            $intro = '<p>Esse tema não existe. Escolha um dos temas abaixo ou veja <a href="/">todas as vagas PHP</a>.</p>';
            return $this->themeHtml($request, 'Tema não encontrado | Vagas PHP', 'Tema de vagas PHP não encontrado.',
                '/vagas', 'Tema não encontrado', '<a href="/vagas">Temas</a>', $intro, [], '',
                $themes->allHtml($counts), noindex: true, status: 404);
        }
        $mine = array_slice(array_values(array_filter($jobs, fn ($j) => Themes::matches($theme, $j))), 0, 100);
        $facets = self::safe(fn () => $this->repo->jobFacets(90), []);
        $last90 = count(array_filter($facets, fn ($j) => Themes::matches($theme, $j)));
        [$intro, $description] = self::themeIntro($theme, $mine, $last90);
        $title = $mine ? "{$theme['name']}: " . Text::plural(count($mine), 'aberta', 'abertas') . ' agora | Vagas PHP'
            : "{$theme['name']} | Vagas PHP";
        $params = array_filter(['stack' => $theme['stack'], 'workplace' => $theme['workplace'], 'seniority' => $theme['seniority']]);
        $more = $mine ? '<a href="/?' . Text::e(Text::query($params)) . '">Ver na página inicial, com filtros e '
            . 'atualização automática</a>' : '';
        $related = '<section class="themes"><h2>Temas relacionados</h2><nav>'
            . Themes::links($themes->related($theme, $counts), $counts)
            . '<a href="/vagas">Todos os temas</a></nav></section>';
        $jsonld = [Seo::breadcrumbs($request, ['Vagas PHP', '/'], ['Temas', '/vagas'], [$theme['name'], $theme['path']])];
        if ($mine) {
            $jsonld[] = $this->jobList($request, $theme['name'], $mine);
        }
        return $this->themeHtml($request, $title, $description, $theme['path'], $theme['name'],
            '<a href="/vagas">Temas</a> › ' . Text::e($theme['name']), $intro, $mine, $more, $related, $jsonld);
    }

    // --- páginas -------------------------------------------------------------------------

    /** Filtros de /api/jobs (e da home, que mostra a mesma lista no HTML). */
    private static function jobFilters(Request $r): array
    {
        return ['q' => $r->get('q') ?: null, 'workplace' => $r->get('workplace') ?: null,
            'seniority' => $r->get('seniority') ?: null, 'stack' => $r->get('stack') ?: null,
            'hours' => self::number($r->get('hours'), 72, 1, 72),
            'includeClosed' => in_array($r->get('include_closed'), ['1', 'true'], true)];
    }

    /**
     * Marca no formulário da home os filtros da URL (/?stack=Laravel), para a página sem
     * JavaScript mostrar o que a lista está filtrando. O JavaScript lê os mesmos da URL.
     */
    private function formState(string $html, Request $r): string
    {
        foreach (['workplace', 'seniority', 'stack', 'hours'] as $name) {
            if (!($value = $r->get($name))) {
                continue;
            }
            if (!preg_match("#<select name=\"$name\".*?</select>#s", $html, $m, PREG_OFFSET_CAPTURE)) {
                continue;
            }
            [$select, $start] = $m[0];
            $options = str_replace(' selected>', '>', $select);
            $v = preg_quote(Text::e($value), '#');
            // <option>Remoto</option> ou <option value="24">...</option>
            $chosen = preg_replace_callback("#<option( value=\"$v\">|>$v<)#",
                fn ($o) => Seo::replaceOnce('<option', '<option selected', $o[0]), $options, 1);
            if ($chosen !== $options) {
                $html = substr_replace($html, $chosen, $start, strlen($select));
            }
        }
        if (in_array($source = $r->get('source'), $this->repo->sources(), true)) {
            $html = Seo::replaceOnce('name="source" value="" checked', 'name="source" value=""', $html);
            $html = Seo::replaceOnce("name=\"source\" value=\"$source\"", "name=\"source\" value=\"$source\" checked", $html);
        }
        if ($q = $r->get('q')) {
            $html = Seo::replaceOnce('<input type="search" name="q"', '<input type="search" name="q" value="' . Text::e($q) . '"', $html);
        }
        return $html;
    }

    public function index(Request $r): Response
    {
        $source = in_array($r->get('source'), $this->repo->sources(), true) ? $r->get('source') : null;
        [$rows, $st] = self::safe(fn () => [
            $this->repo->withClicks(self::withPath($this->repo->queryJobs(...['source' => $source,
                ...self::jobFilters($r), 'limit' => self::PAGE]))),
            $this->repo->stats(),
        ], [[], ['open_total' => 0, 'last_runs' => []]]);
        $total = $st['open_total'];
        $statsHtml = "<span><b>$total</b> vagas abertas na base</span>";
        $runs = [];
        foreach ($st['last_runs'] as $run) {
            if ($run && $run['ok']) {
                $runs[] = $run['finished_at'];
            }
        }
        sort($runs, SORT_STRING);
        if ($runs) {
            $statsHtml .= '<span>última coleta ' . Text::e(self::ago(end($runs)) ?? '') . '</span>';
        }
        $hours = in_array($r->get('hours'), ['1', '4', '6', '24', '48'], true) ? $r->get('hours') : '72';
        $statsHtml .= '<span class="period">últim' . ($hours === '1' ? 'a' : 'as') . " $hours hora" . ($hours !== '1' ? 's' : '') . '</span>';

        $themes = $this->themes();
        $counts = $themes->counts($this->openJobs());  // contagem dos temas: sempre sem filtro
        $singles = array_filter($themes->themes, fn ($t) => $t['group'] !== 'Combinações');
        $themesHtml = Themes::links($singles, $counts) . '<a href="/vagas">Todos os temas</a>';
        $title = 'Vagas PHP, Laravel e Symfony — remotas e no Brasil | Vagas PHP';
        $description = "$total vagas PHP abertas, publicadas nas últimas " . (int) Dates::maxAgeHours() . ' h: '
            . 'Laravel, Symfony, WordPress e mais, remotas, híbridas e presenciais. '
            . 'Do LinkedIn, Gupy, Sólides, Catho, Remotar e outros sites, atualizadas '
            . 'várias vezes por dia.';
        $base = Seo::siteUrl($r);
        $jsonld = [['@context' => 'https://schema.org', '@type' => 'WebSite', 'name' => Seo::SITE_NAME,
            'url' => $base . '/', 'inLanguage' => 'pt-BR'], $this->jobList($r, 'Vagas PHP abertas', $rows)];
        $list = implode('', array_map(fn ($j) => self::jobCard($j), $rows))
            ?: '<li class="empty">Nenhuma vaga encontrada com esses filtros.</li>';
        $html = Seo::render($r, 'index.html', $title, $description, '/',
            ['list' => $list, 'stats' => $statsHtml, 'themes' => $themesHtml], $jsonld);
        return Response::html($this->formState($html, $r));
    }

    public function jobs(Request $r): Response
    {
        $source = $r->get('source') ?: null;
        if ($source && !in_array($source, $this->repo->sources(), true)) {
            return Response::json(['error' => 'source deve ser ' . implode(', ', $this->repo->sources())], 400);
        }
        $limit = (int) self::number($r->get('limit'), 50, 1, 200);
        $rows = self::safe(fn () => $this->repo->queryJobs(...['source' => $source, ...self::jobFilters($r),
            'limit' => $limit + 1, 'offset' => (int) self::number($r->get('offset'), 0, 0, 1e6)]), []);
        $jobs = array_map(Repo::publicJob(...), $this->repo->withClicks(self::withPath(array_slice($rows, 0, $limit))));
        return Response::json(['jobs' => $jobs,
            'has_more' => count($rows) > $limit, 'max_age_hours' => Dates::maxAgeHours()]);
    }

    public function dashboardPage(Request $r): Response
    {
        $total = self::safe(fn () => $this->repo->openCount(), 0);
        $description = "Mercado de vagas PHP em números: $total vagas abertas nas últimas "
            . (int) Dates::maxAgeHours() . ' h, vagas novas por dia, por site, modalidade, '
            . 'senioridade, contratação, stack e empresas.';
        return Response::html(Seo::render($r, 'dashboard.html',
            'Dashboard de vagas PHP: vagas por dia, stack e modalidade | Vagas PHP', $description, '/dashboard',
            jsonld: Seo::breadcrumbs($r, ['Vagas PHP', '/'], ['Dashboard', '/dashboard'])));
    }

    public function dashboard(Request $r): Response
    {
        $days = (int) self::number($r->get('days'), 14, 3, 90);
        // Próximas coletas: o coletor grava em site_meta "schedule" a cada minuto.
        $data = self::safe(fn () => $this->repo->dashboard($days) + ['schedule' => $this->repo->meta('schedule')], null);
        return $data === null ? Response::json(['error' => 'base ainda vazia'], 503) : Response::json($data);
    }

    /**
     * Separa uma expressão regular nas alternativas de primeiro nível ("a|b|(c|d)" -> a, b,
     * (c|d)), tirando o grupo e os \b que envolvem tudo: fica mais fácil de ler.
     *
     * @return list<string>
     */
    public static function alternatives(string $rx): array
    {
        $s = str_starts_with($rx, '\\b') ? substr($rx, 2) : $rx;
        $s = str_ends_with($s, '\\b') ? substr($s, 0, -2) : $s;
        if (str_starts_with($s, '(') && str_ends_with($s, ')')) {
            [$depth, $i, $wrapped, $len] = [0, 0, true, strlen($s)];
            while ($i < $len) {
                if ($s[$i] === '\\') {
                    $i += 2;
                    continue;
                }
                if ($s[$i] === '(') {
                    $depth++;
                } elseif ($s[$i] === ')') {
                    $depth--;
                    if ($depth === 0 && $i < $len - 1) {
                        $wrapped = false;
                        break;
                    }
                }
                $i++;
            }
            if ($wrapped) {
                $s = substr($s, 1, -1);
                $s = str_starts_with($s, '?:') ? substr($s, 2) : $s;
            }
        }
        [$parts, $depth, $cur, $i, $len] = [[], 0, '', 0, strlen($s)];
        while ($i < $len) {
            $c = $s[$i];
            if ($c === '\\') {
                $cur .= substr($s, $i, 2);
                $i += 2;
                continue;
            }
            if ($c === '(' || $c === '[') {
                $depth++;
            } elseif ($c === ')' || $c === ']') {
                $depth--;
            }
            if ($c === '|' && $depth === 0) {
                $parts[] = $cur;
                $cur = '';
            } else {
                $cur .= $c;
            }
            $i++;
        }
        $parts[] = $cur;
        return array_values(array_filter($parts, fn ($p) => $p !== ''));
    }

    private function rulesHtml(array $counts): string
    {
        $rules = $this->repo->meta('rules') ?? [];
        $out = '';
        foreach (self::RULE_GROUPS as [$key, $title, $note]) {
            $out .= '<h2>' . Text::e($title) . '</h2><p class="group-note">' . Text::e($note) . '</p>';
            $i = 0;
            foreach ($rules as $r) {
                if ($r['group'] !== $key) {
                    continue;
                }
                $i++;
                $n = $counts[$r['id']] ?? null;
                $badge = $r['effect'] === 'aceita' ? '✓ aceita' : '✕ recusa';
                $count = $n !== null ? '<span class="count">' . Text::fmt($n) . ' na base</span>' : '';
                $chips = '';
                foreach ($r['patterns'] as $p) {
                    foreach (self::alternatives($p) as $a) {
                        $chips .= '<code>' . Text::e($a) . '</code>';
                    }
                }
                $details = $r['patterns'] ? "<details><summary>Expressões usadas</summary><div class=\"chips\">$chips</div></details>" : '';
                $out .= "<section class=\"card rule\"><div class=\"n\">$i</div><div><h3>" . Text::e($r['title'])
                    . "<span class=\"badge {$r['effect']}\">$badge</span>$count</h3><p>" . Text::e($r['text'])
                    . "</p>$details</div></section>";
            }
        }
        return $out;
    }

    private static function dismissedHtml(array $dismissed): string
    {
        if (!$dismissed) {
            return '<p style="margin:0;color:var(--muted)">Nenhuma até agora.</p>';
        }
        $rows = '<table><tr><th>Quando</th><th>Item</th><th>Motivo</th></tr>';
        foreach ($dismissed as $j) {
            [$at, $reason] = array_pad(explode(' ', $j['dismissed'], 2), 2, '');
            $when = Dates::parse($at);
            $when = $when ? Dates::local($when)->format('d/m/Y H:i') : $at;
            $url = Text::safeUrl($j['url'] ?? null);
            $title = Text::e($j['title'] ?: ($j['url'] ?: '—'));
            $item = $url ? '<a href="' . Text::e($url) . "\" target=\"_blank\" rel=\"noopener\">$title</a>" : $title;
            $rows .= '<tr><td>' . Text::e($when) . "</td><td>$item</td><td>" . Text::e($reason ?: '—') . '</td></tr>';
        }
        return $rows . '</table>';
    }

    private function ruleStats(): array
    {
        return self::safe(fn () => $this->repo->ruleStats(), ['counts' => (object) [], 'dismissed' => []]);
    }

    public function rulesPage(Request $r): Response
    {
        $stats = $this->ruleStats();
        return Response::html(Seo::render($r, 'regras.html',
            'Como as vagas PHP são filtradas: as regras do site | Vagas PHP',
            'As regras que decidem quais vagas e publicações de PHP, Laravel e Symfony '
            . 'aparecem no site, geradas do próprio código do filtro, e os sites que não '
            . 'coletamos.', '/regras',
            ['max_age' => (string) (int) Dates::maxAgeHours(), 'groups' => $this->rulesHtml((array) $stats['counts']),
                'dismissed' => self::dismissedHtml($stats['dismissed'])],
            Seo::breadcrumbs($r, ['Vagas PHP', '/'], ['Regras', '/regras'])));
    }

    public function rules(Request $r): Response
    {
        $rules = self::safe(fn () => $this->repo->meta('rules'), null) ?? [];
        return Response::json(['rules' => $rules] + $this->ruleStats() + ['max_age_hours' => Dates::maxAgeHours()]);
    }

    private static function brDate(?string $iso): string
    {
        $when = Dates::parse($iso);
        return $when ? Dates::local($when)->format('d/m/Y') : '';
    }

    public function recruitersList(): array
    {
        return self::safe(fn () => $this->repo->recruiters(self::RECRUITERS_DAYS, self::recruitersMin(), self::recruitersHide()), []);
    }

    private static function recruiterCard(array $p, int $i): string
    {
        $e = Text::e(...);
        $url = Text::safeUrl($p['url']);
        $name = $e($p['name'] ?: $p['url']);
        $name = $url ? '<a href="' . $e($url) . "\" target=\"_blank\" rel=\"nofollow noopener\">$name</a>" : $name;
        $headline = $p['headline'] ? '<p class="headline">' . $e($p['headline']) . '</p>' : '';
        $chips = $p['stack'] ? '<div class="chips">' . implode('', array_map(fn ($s) => '<span class=chip>' . $e($s) . '</span>', $p['stack'])) . '</div>' : '';
        return "<section class=\"card person\"><div class=\"n\">$i</div><div><h2>$name</h2>"
            . "$headline<p class=\"meta\">Última vaga em " . self::brDate($p['last_posted']) . "</p>$chips"
            . "</div><div class=\"jobs\"><b>{$p['jobs']}</b><span>" . ($p['jobs'] === 1 ? 'vaga' : 'vagas')
            . '</span></div></section>';
    }

    public function recruitersPage(Request $r): Response
    {
        $people = $this->recruitersList();
        $cards = '';
        foreach ($people as $i => $p) {
            $cards .= self::recruiterCard($p, $i + 1);
        }
        $cards = $cards ?: '<section class="card"><p style="margin:0;color:var(--muted)">Ainda não há recrutadores '
            . 'com vagas suficientes no período. Volte em alguns dias.</p></section>';
        $description = Text::plural(count($people), 'tech recruiter', 'tech recruiters') . ' que mais '
            . 'publicaram vagas PHP, Laravel e Symfony no LinkedIn nos últimos '
            . self::RECRUITERS_DAYS . ' dias. Siga esses perfis para ver as vagas assim que saem.';
        return Response::html(Seo::render($r, 'recrutadores.html',
            'Tech recruiters de vagas PHP para seguir no LinkedIn | Vagas PHP', $description, '/recrutadores',
            ['list' => $cards, 'days' => (string) self::RECRUITERS_DAYS, 'min' => (string) self::recruitersMin()],
            Seo::breadcrumbs($r, ['Vagas PHP', '/'], ['Recrutadores', '/recrutadores'])));
    }

    public function recruiters(Request $r): Response
    {
        return Response::json(['recruiters' => $this->recruitersList(), 'days' => self::RECRUITERS_DAYS,
            'min_jobs' => self::recruitersMin()]);
    }

    public function companiesList(): array
    {
        return self::safe(fn () => $this->repo->companies(self::COMPANIES_DAYS, self::COMPANIES_MIN), []);
    }

    private static function companyCard(array $c, int $i): string
    {
        $e = Text::e(...);
        $remote = 0;
        foreach ($c['workplace'] as [$w, $n]) {
            if ($w === 'Remoto') {
                $remote = $n;
            }
        }
        $meta = ['Última vaga em ' . self::brDate($c['last_posted'])];
        if ($remote) {
            $meta[] = $remote === $c['jobs'] ? 'todas remotas' : Text::plural($remote, 'remota', 'remotas');
        }
        $sources = array_map(function ($s) {
            $name = self::SOURCE_NAMES[$s] ?? $s;
            return str_starts_with($name, 'Vaga ') ? substr($name, 5) : $name;
        }, $c['sources']);
        $chips = [...$c['stack'], ...$sources];
        $openLink = '';
        $when = Dates::parse($c['last_posted']);
        if ($when && Dates::secondsSince($when) < Dates::maxAgeHours() * 3600) {
            $openLink = '<p class="meta"><a href="/?' . $e(Text::query(['q' => $c['name']])) . '">Ver vagas abertas</a></p>';
        }
        $text = Text::fold(implode(' ', [$c['name'], ...$c['stack'], ...$c['sources'], ...array_column($c['workplace'], 0)]));
        return '<section class="card company" data-text="' . $e($text) . "\"><div class=\"n\">$i</div><div>"
            . '<h2>' . $e($c['name']) . '</h2><p class="meta">' . $e(implode(' · ', $meta)) . '</p><div class="chips">'
            . implode('', array_map(fn ($s) => '<span class=chip>' . $e($s) . '</span>', $chips)) . "</div>$openLink</div>"
            . "<div class=\"jobs\"><b>{$c['jobs']}</b><span>" . ($c['jobs'] === 1 ? 'vaga' : 'vagas')
            . '</span></div></section>';
    }

    public function companiesPage(Request $r): Response
    {
        $rows = $this->companiesList();
        $cards = '';
        foreach ($rows as $i => $c) {
            $cards .= self::companyCard($c, $i + 1);
        }
        $cards = $cards ?: '<section class="card"><p style="margin:0;color:var(--muted)">Ainda não há empresas com '
            . 'vagas suficientes no período.</p></section>';
        $top = $rows ? Text::joinAnd(array_map(fn ($c) => "{$c['name']} ({$c['jobs']})", array_slice($rows, 0, 3))) : '';
        $description = 'Ranking de ' . Text::plural(count($rows), 'empresa', 'empresas') . ' que mais anunciaram '
            . 'vagas PHP, Laravel e Symfony nos últimos ' . self::COMPANIES_DAYS . ' dias' . ($top ? ": $top." : '.');
        $base = Seo::siteUrl($r);
        $items = [];
        foreach (array_slice($rows, 0, 50) as $i => $c) {
            $items[] = ['@type' => 'ListItem', 'position' => $i + 1, 'item' => ['@type' => 'Organization', 'name' => $c['name']]];
        }
        $jsonld = [Seo::breadcrumbs($r, ['Vagas PHP', '/'], ['Empresas', '/empresas']),
            ['@context' => 'https://schema.org', '@type' => 'ItemList', 'name' => 'Empresas que mais anunciam vagas PHP',
                'url' => $base . '/empresas', 'itemListElement' => $items]];
        return Response::html(Seo::render($r, 'empresas.html', 'Empresas que mais contratam devs PHP | Vagas PHP',
            $description, '/empresas',
            ['list' => $cards, 'days' => (string) self::COMPANIES_DAYS, 'min' => (string) self::COMPANIES_MIN], $jsonld));
    }

    public function companies(Request $r): Response
    {
        return Response::json(['companies' => $this->companiesList(), 'days' => self::COMPANIES_DAYS,
            'min_jobs' => self::COMPANIES_MIN, 'max_age_hours' => Dates::maxAgeHours()]);
    }

    public function contatoPage(Request $r): Response
    {
        return Response::html(Seo::render($r, 'contato.html',
            'Contato: vaga em destaque, correções e sugestões | Vagas PHP',
            'Fale com quem mantém o Vagas PHP pelo LinkedIn para anunciar uma vaga em '
            . 'destaque, corrigir ou remover uma vaga, ou sugerir uma fonte nova.', '/contato',
            jsonld: Seo::breadcrumbs($r, ['Vagas PHP', '/'], ['Contato', '/contato'])));
    }

    public function stats(Request $r): Response
    {
        return Response::json(self::safe(fn () => $this->repo->stats(),
            ['sources' => (object) [], 'last_runs' => (object) [], 'open_total' => 0]));
    }

    // --- cliques no anúncio original -----------------------------------------------------

    /**
     * Conta o clique e redireciona para o anúncio original da vaga `job`, o que está na base:
     * o `url` do link não decide o destino (senão o /out redireciona para qualquer site).
     * Vaga desconhecida ou sem anúncio: home. Robô (isBot) e HEAD são redirecionados sem
     * contar: o número aparece nos cards.
     */
    public function out(Request $r): Response
    {
        $job = ($id = $r->get('job')) ? self::safe(fn () => $this->repo->clickTarget($id), null) : null;
        if (!($url = Text::safeUrl($job['url'] ?? null))) {
            return Response::redirect('/', 302);
        }
        if ($r->method === 'GET' && !self::isBot($r->headers['user-agent'] ?? null)) {
            $this->repo->logClick($job['id'], $url, self::clickPage($r->get('page')), $job['source'], self::visitor($r));
        }
        return Response::redirect($url, 302, ['Cache-Control' => 'no-store']);
    }

    /** Página do site de onde saiu o clique: só caminho ("/vagas/laravel"); o resto não grava. */
    public static function clickPage(?string $page): ?string
    {
        return $page !== null && str_starts_with($page, '/') && !str_starts_with($page, '//') ? $page : null;
    }

    /**
     * Quem clicou, para contar um clique por vaga e visitante por dia (chave única
     * job_id + visitor em clicks): HMAC do IP e do user agent com o dia em Brasília. Muda
     * todo dia (não liga visitas de dias diferentes) e, sem a chave, não volta ao IP. A
     * chave é o DATABASE_URL, segredo que o site já tem. IP: o do Cloudflare
     * (CF-Connecting-IP), senão o primeiro do X-Forwarded-For, senão o de quem conectou.
     */
    public static function visitor(Request $r): string
    {
        $ip = trim(explode(',', $r->header('cf-connecting-ip') ?? $r->header('x-forwarded-for') ?? $r->ip)[0]);
        $day = Dates::local(Dates::now())->format('Y-m-d');
        $ua = (string) $r->header('user-agent');
        return substr(hash_hmac('sha256', "$day|$ip|$ua", (string) getenv('DATABASE_URL')), 0, 16);
    }

    /** Crawler, pré-visualização de link, verificador ou cliente HTTP (sem user agent também). */
    public static function isBot(?string $userAgent): bool
    {
        // Navegador de app (LinkedInApp, Instagram, FBAV...) é gente: só os robôs desses apps entram.
        return trim((string) $userAgent) === '' || (bool) preg_match('/bot\b|bot\/|crawl|spider|slurp|'
            . 'preview|externalhit|facebookcatalog|whatsapp|embedly|headless|lighthouse|pingdom|uptime|'
            . 'monitor|scan|curl|wget|python|java\/|go-http|okhttp|axios|node-fetch|undici|httpclient|'
            . 'libwww|scrapy/i', (string) $userAgent);
    }

    public function clicks(Request $r): Response
    {
        $days = (int) self::number($r->get('days'), 7, 1, 365);
        $data = self::safe(fn () => $this->repo->clickStats($days),
            ['total' => 0, 'by_job' => [], 'by_source' => [], 'by_day' => []]);
        return Response::json($data + ['days' => $days]);
    }

    // --- sitemap e robots ----------------------------------------------------------------
    // Cada provedor devolve [[caminho, lastmod ISO ou null]]; caminho repetido vale uma vez.

    private static function newest(array $jobs): ?string
    {
        $dates = array_map(fn ($j) => $j['posted_at'] ?: $j['first_seen'], $jobs);
        return $dates ? max($dates) : null;
    }

    /** @return list<array{string, ?string}> */
    private function sitemapEntries(): array
    {
        $jobs = $this->openJobs();
        $newest = self::newest($jobs);
        $out = [];
        foreach (self::PAGES as $path) {
            $out[] = [$path, in_array($path, ['/', '/vagas'], true) ? $newest : null];
        }
        foreach ($this->themes()->themes as $t) {
            $out[] = [$t['path'], self::newest(array_filter($jobs, fn ($j) => Themes::matches($t, $j)))];
        }
        foreach (self::safe(fn () => $this->repo->openPortalJobs(), []) as $row) {
            $out[] = [Seo::jobPath($row), $row['posted']];
        }
        return $out;
    }

    public function sitemap(Request $r): Response
    {
        $base = Seo::siteUrl($r);
        $entries = [];
        foreach ($this->sitemapEntries() as [$path, $lastmod]) {
            if (!array_key_exists($path, $entries)) {
                $entries[$path] = $lastmod;
            }
        }
        $urls = [];
        foreach ($entries as $path => $lastmod) {
            $mod = $lastmod ? '<lastmod>' . Text::e($lastmod) . '</lastmod>' : '';
            $urls[] = '<url><loc>' . Text::e($base . $path) . "</loc>$mod</url>";
        }
        $xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            . "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
            . implode("\n", $urls) . "\n</urlset>\n";
        return Response::text($xml, 'application/xml');
    }

    /**
     * Sem "Disallow: /api/": bloquear por robots.txt impede o Googlebot de buscar os dados
     * que a home usa para renderizar. O JSON fica fora do índice pelo X-Robots-Tag.
     */
    public function robots(Request $r): Response
    {
        // /out só redireciona para o anúncio e conta o clique: crawler fica fora.
        return Response::text("User-agent: *\nAllow: /\nDisallow: /out\n\nSitemap: " . Seo::siteUrl($r) . "/sitemap.xml\n");
    }

    private function asset(string $name, string $type): Response
    {
        return new Response((string) file_get_contents("{$this->assets}/$name"), 200,
            ['Content-Type' => $type, 'Cache-Control' => 'public, max-age=86400']);
    }
}
