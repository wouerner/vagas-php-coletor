<?php

declare(strict_types=1);

namespace VagasPhp;

use VagasPhp\Http\Request;

/**
 * Páginas para buscadores e robôs de IA: título, descrição, canonical, Open Graph e
 * JSON-LD no <head>, e conteúdo já renderizado no servidor (robôs como os da OpenAI não
 * executam JavaScript). Os templates marcam onde entra o conteúdo com <!--ssr:nome-->;
 * render() troca cada marca pelo HTML de `content`.
 *
 * VAGAS_SITE_URL (ex.: https://vagas.seudominio.com) fixa o endereço público usado no
 * canonical e no sitemap; sem ela, vem dos cabeçalhos do proxy (X-Forwarded-*).
 * VAGAS_ORIGIN_TRIAL: token do origin trial do WebMCP no Chrome (vale para uma origem).
 * Com vários sites no container (VAGAS_SITES), o endereço vem de Sites e cada site pode ter
 * o próprio token e GA (VAGAS_ORIGIN_TRIAL_RUBY, VAGAS_GA_ID_LUA...).
 * Nome, ícone e textos de marca vêm de Brand (VAGAS_TENANT): os templates passam por
 * Brand::fill() antes do conteúdo do servidor entrar (dado da base não vira marca).
 */
final class Seo
{
    /** Nome público do site ("Vagas PHP", "Vagas Ruby"): og:site_name, títulos e JSON-LD. */
    public static function siteName(): string
    {
        return Brand::name();
    }

    /** Texto alternativo do preview social (LinkedIn, Telegram, WhatsApp), ou null sem imagem. */
    public static function ogImageAlt(): ?string
    {
        return Brand::get('og_alt');
    }

    public static function templates(): string
    {
        return dirname(__DIR__) . '/templates';
    }

    /** Variável do site atual (Sites::env: VAGAS_GA_ID_RUBY no lugar de VAGAS_GA_ID...). */
    private static function env(string $name): string
    {
        return Sites::env($name);
    }

    /** Google Analytics (G-XXXXXXXXXX) ou Tag Manager (GTM-XXXXXXX); vazio ou inválido: sem GA. */
    public static function gaId(): string
    {
        $id = self::env('VAGAS_GA_ID');
        return preg_match('/^(G|GTM)-[A-Z0-9]{4,20}$/', $id) ? $id : '';
    }

    /** Endereço público do site, sem barra no fim. */
    public static function siteUrl(Request $request): string
    {
        if (($fixed = self::publicUrl()) !== '') {
            return $fixed;
        }
        $proto = trim(explode(',', $request->header('x-forwarded-proto') ?? $request->scheme)[0]);
        $host = trim(explode(',', $request->header('x-forwarded-host') ?? $request->host)[0]);
        return "$proto://$host";
    }

    /** Endereço público conhecido sem a requisição (Sites ou VAGAS_SITE_URL), ou '' sem nenhum dos dois. */
    public static function publicUrl(): string
    {
        return Sites::url() ?? rtrim(self::env('VAGAS_SITE_URL'), '/');  // vários sites: o domínio da lista
    }

    /** JSON para <script type="application/ld+json">: "</" escapado não fecha o script. */
    public static function jsonLd(array $data): string
    {
        $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR);
        return str_replace('</', '<\\/', $json);
    }

    /**
     * Tags do <head>. `path` é o caminho canônico ("/vagas/laravel"), sem query string.
     *
     * @param array|null $jsonld um objeto JSON-LD ou uma lista deles
     */
    public static function head(Request $request, string $title, string $description, string $path,
                                ?array $jsonld = null, bool $noindex = false): string
    {
        $base = self::siteUrl($request);
        $og = Brand::get('og_image');
        [$t, $d, $u] = [Text::e($title), Text::e($description), Text::e($base . $path)];
        $img = $og === null ? null : Text::e($base . $og);
        $tags = [
            "<title>$t</title>",
            "<meta name=\"description\" content=\"$d\">",
            "<link rel=\"canonical\" href=\"$u\">",
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="' . Text::e(self::siteName()) . '">',
            '<meta property="og:locale" content="pt_BR">',
            "<meta property=\"og:title\" content=\"$t\">",
            "<meta property=\"og:description\" content=\"$d\">",
            "<meta property=\"og:url\" content=\"$u\">",
        ];
        if ($img !== null) {
            array_push($tags,
                "<meta property=\"og:image\" content=\"$img\">",
                '<meta property="og:image:width" content="1200">',
                '<meta property="og:image:height" content="630">',
                '<meta property="og:image:alt" content="' . Text::e((string) self::ogImageAlt()) . '">',
            );
        }
        $tags[] = '<meta name="twitter:card" content="' . ($img !== null ? 'summary_large_image' : 'summary') . '">';
        $tags[] = "<meta name=\"twitter:title\" content=\"$t\">";
        $tags[] = "<meta name=\"twitter:description\" content=\"$d\">";
        if ($img !== null) {
            $tags[] = "<meta name=\"twitter:image\" content=\"$img\">";
        }
        if (($token = self::env('VAGAS_ORIGIN_TRIAL')) !== '') {
            array_unshift($tags, '<meta http-equiv="origin-trial" content="' . Text::e($token) . '">');
        }
        if ($noindex) {
            $tags[] = '<meta name="robots" content="noindex">';
        }
        $items = $jsonld === null ? [] : (array_is_list($jsonld) ? $jsonld : [$jsonld]);
        foreach ($items as $data) {
            $tags[] = '<script type="application/ld+json">' . self::jsonLd($data) . '</script>';
        }
        return implode("\n", $tags);
    }

    /** Template sem conteúdo do servidor, só com a tag do GA (fora de ?print=1). */
    public static function plain(Request $request, string $name): string
    {
        return self::withAnalytics($request, self::withTabs($request, self::template($name)));
    }

    /** Abas dos outros sites (Sites::tabs) logo depois do <body>, fora de ?print=1. */
    private static function withTabs(Request $request, string $html): string
    {
        $tabs = $request->has('print') ? '' : Sites::tabs();
        return $tabs === '' ? $html
            : (string) preg_replace_callback('#<body[^>]*>#', fn ($m) => $m[0] . "\n" . $tabs, $html, 1);
    }

    /**
     * Ícone do Reddit (Simple Icons, CC0) antes de todo link com class="reddit": cards, página
     * da vaga e rodapé. Entra em todas as páginas, que não têm folha de estilo em comum.
     */
    private const REDDIT_STYLE = '<style>'
        . 'a.reddit { white-space: nowrap; } p.reddit a.reddit { display: inline-block; white-space: normal; } a.reddit::before { content: ""; display: inline-block; width: 1.15em; height: 1.15em; margin-right: .3em; vertical-align: -.22em; background: url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\'%3E%3Cpath fill=\'%23FF4500\' d=\'M12 0C5.373 0 0 5.373 0 12c0 3.314 1.343 6.314 3.515 8.485l-2.286 2.286C.775 23.225 1.097 24 1.738 24H12c6.627 0 12-5.373 12-12S18.627 0 12 0Zm4.388 3.199c1.104 0 1.999.895 1.999 1.999 0 1.105-.895 2-1.999 2-.946 0-1.739-.657-1.947-1.539v.002c-1.147.162-2.032 1.15-2.032 2.341v.007c1.776.067 3.4.567 4.686 1.363.473-.363 1.064-.58 1.707-.58 1.547 0 2.802 1.254 2.802 2.802 0 1.117-.655 2.081-1.601 2.531-.088 3.256-3.637 5.876-7.997 5.876-4.361 0-7.905-2.617-7.998-5.87-.954-.447-1.614-1.415-1.614-2.538 0-1.548 1.255-2.802 2.803-2.802.645 0 1.239.218 1.712.585 1.275-.79 2.881-1.291 4.64-1.365v-.01c0-1.663 1.263-3.034 2.88-3.207.188-.911.993-1.595 1.959-1.595Zm-8.085 8.376c-.784 0-1.459.78-1.506 1.797-.047 1.016.64 1.429 1.426 1.429.786 0 1.371-.369 1.418-1.385.047-1.017-.553-1.841-1.338-1.841Zm7.406 0c-.786 0-1.385.824-1.338 1.841.047 1.017.634 1.385 1.418 1.385.785 0 1.473-.413 1.426-1.429-.046-1.017-.721-1.797-1.506-1.797Zm-3.703 4.013c-.974 0-1.907.048-2.77.135-.147.015-.241.168-.183.305.483 1.154 1.622 1.964 2.953 1.964 1.33 0 2.47-.81 2.953-1.964.057-.137-.037-.29-.184-.305-.863-.087-1.795-.135-2.769-.135Z\'/%3E%3C/svg%3E") no-repeat center / contain; }'
        . "</style>\n";

    /** Template com as marcas {{brand:...}} do tenant já trocadas (Brand::fill). */
    public static function template(string $name): string
    {
        $html = Brand::fill((string) file_get_contents(self::templates() . "/$name"));
        return (string) preg_replace('#</head>#', self::REDDIT_STYLE . '</head>', $html, 1);
    }

    private static function withAnalytics(Request $request, string $html): string
    {
        $ga = self::gaId();
        if ($ga !== '' && !$request->has('print')) {
            $gtm = str_starts_with($ga, 'GTM-');
            $tag = strtr((string) file_get_contents(self::templates() . '/analytics.html'), [
                '{GA_INIT}' => $gtm
                    ? 'dataLayer.push({"gtm.start": Date.now(), event: "gtm.js"});'
                    : 'gtag("config", "' . $ga . '");',
                '{GA_SRC}' => 'https://www.googletagmanager.com/' . ($gtm ? 'gtm.js' : 'gtag/js') . '?id=' . $ga,
            ]);
            $html = self::replaceOnce('</head>', $tag . '</head>', $html);
        }
        return $html;
    }

    public static function replaceOnce(string $search, string $replace, string $subject): string
    {
        $pos = strpos($subject, $search);
        return $pos === false ? $subject : substr_replace($subject, $replace, $pos, strlen($search));
    }

    /**
     * HTML do template com o <head> de head(), as marcas <!--ssr:nome--> trocadas pelo
     * HTML de `content` (já escapado por quem chama), a tag do GA e o /webmcp.js
     * (ferramentas para agentes de IA, WebMCP), esses dois fora de ?print=1.
     *
     * @param array<string, string> $content
     */
    public static function render(Request $request, string $name, string $title, string $description,
                                  string $path, array $content = [], ?array $jsonld = null,
                                  bool $noindex = false): string
    {
        $html = self::template($name);
        $html = preg_replace('#\s*<title>.*?</title>|\s*<meta name="description"[^>]*>#s', '', $html);
        $tags = self::head($request, $title, $description, $path, $jsonld, $noindex);
        $html = self::replaceOnce('</head>', $tags . "\n</head>", $html);
        foreach ($content as $key => $value) {
            $html = str_replace("<!--ssr:$key-->", $value, $html);
        }
        if (!$request->has('print')) {
            $html = self::replaceOnce('</head>', "<script defer src=\"/webmcp.js\"></script>\n</head>", $html);
        }
        return self::withAnalytics($request, self::withTabs($request, $html));
    }

    /**
     * Página da vaga no site (/vaga/<seq>-<título>), só para vagas de portais: posts do
     * LinkedIn não são anúncios estruturados. O número (seq) identifica a vaga; o título
     * no endereço é só para leitura. Contrato com o coletor (indexing.job_path).
     */
    public static function jobPath(array $job): ?string
    {
        if (($job['source'] ?? null) === 'post' || empty($job['seq'])) {
            return null;
        }
        return "/vaga/{$job['seq']}-" . Text::slugify($job['title'] ?? null);
    }

    /** JSON-LD BreadcrumbList a partir de pares [nome, caminho]. */
    public static function breadcrumbs(Request $request, array ...$items): array
    {
        $base = self::siteUrl($request);
        $list = [];
        foreach (array_values($items) as $i => [$name, $path]) {
            $list[] = ['@type' => 'ListItem', 'position' => $i + 1, 'name' => $name, 'item' => $base . $path];
        }
        return ['@context' => 'https://schema.org', '@type' => 'BreadcrumbList', 'itemListElement' => $list];
    }
}
