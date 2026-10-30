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
 */
final class Seo
{
    public const SITE_NAME = 'Vagas PHP';
    // Preview social (LinkedIn, Telegram, WhatsApp): assets/og.png, servida em /og.png.
    public const OG_IMAGE_ALT = 'Vagas PHP — vagas de PHP, Laravel e Symfony';

    public static function templates(): string
    {
        return dirname(__DIR__) . '/templates';
    }

    private static function env(string $name): string
    {
        return trim((string) getenv($name));
    }

    /** Google Analytics (G-XXXXXXXXXX); vazio ou inválido: sem GA. */
    public static function gaId(): string
    {
        $id = self::env('VAGAS_GA_ID');
        return preg_match('/^G-[A-Z0-9]{4,20}$/', $id) ? $id : '';
    }

    /** Endereço público do site, sem barra no fim. */
    public static function siteUrl(Request $request): string
    {
        $fixed = rtrim(self::env('VAGAS_SITE_URL'), '/');
        if ($fixed !== '') {
            return $fixed;
        }
        $proto = trim(explode(',', $request->header('x-forwarded-proto') ?? $request->scheme)[0]);
        $host = trim(explode(',', $request->header('x-forwarded-host') ?? $request->host)[0]);
        return "$proto://$host";
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
        [$t, $d, $u, $img] = [Text::e($title), Text::e($description), Text::e($base . $path), Text::e($base . '/og.png')];
        $tags = [
            "<title>$t</title>",
            "<meta name=\"description\" content=\"$d\">",
            "<link rel=\"canonical\" href=\"$u\">",
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="' . self::SITE_NAME . '">',
            '<meta property="og:locale" content="pt_BR">',
            "<meta property=\"og:title\" content=\"$t\">",
            "<meta property=\"og:description\" content=\"$d\">",
            "<meta property=\"og:url\" content=\"$u\">",
            "<meta property=\"og:image\" content=\"$img\">",
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            '<meta property="og:image:alt" content="' . self::OG_IMAGE_ALT . '">',
            '<meta name="twitter:card" content="summary_large_image">',
            "<meta name=\"twitter:title\" content=\"$t\">",
            "<meta name=\"twitter:description\" content=\"$d\">",
            "<meta name=\"twitter:image\" content=\"$img\">",
        ];
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
        return self::withAnalytics($request, (string) file_get_contents(self::templates() . "/$name"));
    }

    private static function withAnalytics(Request $request, string $html): string
    {
        $ga = self::gaId();
        if ($ga !== '' && !$request->has('print')) {
            $tag = str_replace('{GA_ID}', $ga, (string) file_get_contents(self::templates() . '/analytics.html'));
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
        $html = (string) file_get_contents(self::templates() . "/$name");
        $html = preg_replace('#\s*<title>.*?</title>|\s*<meta name="description"[^>]*>#s', '', $html);
        $tags = self::head($request, $title, $description, $path, $jsonld, $noindex);
        $html = self::replaceOnce('</head>', $tags . "\n</head>", $html);
        foreach ($content as $key => $value) {
            $html = str_replace("<!--ssr:$key-->", $value, $html);
        }
        if (!$request->has('print')) {
            $html = self::replaceOnce('</head>', "<script defer src=\"/webmcp.js\"></script>\n</head>", $html);
        }
        return self::withAnalytics($request, $html);
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
