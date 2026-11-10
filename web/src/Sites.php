<?php

declare(strict_types=1);

namespace VagasPhp;

use VagasPhp\Http\Request;

/**
 * Vários sites num container só, escolhidos pelo domínio (Host) da requisição.
 *
 * VAGAS_SITES lista os domínios e o tenant de cada um, separados por vírgula:
 *   VAGAS_SITES=vagasphp.wouerner.dev=php,vagasruby.wouerner.dev=ruby,vagaslua.wouerner.dev=lua
 * O primeiro é o padrão: Host fora da lista (healthcheck em 127.0.0.1, IP direto) recebe
 * esse site, como antes de existir a lista. O endereço público (canonical, sitemap) vem
 * do domínio da lista, nunca do Host enviado, que o cliente controla.
 *
 * Sem VAGAS_SITES vale o modo de um site por container: VAGAS_TENANT e VAGAS_SITE_URL.
 *
 * Variáveis que mudam por site (env()): VAGAS_ORIGIN_TRIAL e VAGAS_GA_ID. Cada site usa a
 * com o sufixo do tenant (VAGAS_GA_ID_RUBY); a sem sufixo vale só para o site padrão (o
 * primeiro), como no modo de um site: o GA e o token do PHP não vão parar no Ruby.
 */
final class Sites
{
    /** @var array{host: string, tenant: string, default: bool}|null site da requisição atual */
    private static ?array $current = null;

    /** @var array<string, string> domínio -> tenant de todos os sites (VAGAS_SITES) */
    private static array $all = [];

    /** @return array<string, string> domínio -> tenant, na ordem de VAGAS_SITES */
    public static function map(?string $spec = null): array
    {
        $spec ??= (string) getenv('VAGAS_SITES');
        $out = [];
        foreach (explode(',', $spec) as $item) {
            [$host, $tenant] = array_pad(array_map('trim', explode('=', $item, 2)), 2, '');
            $host = self::normalize($host);
            $tenant = strtolower($tenant);
            if ($host !== '' && preg_match('/^[a-z0-9_-]+$/', $tenant)) {
                $out[$host] = $tenant;
            }
        }
        return $out;
    }

    /** "VagasRuby.wouerner.dev:443" -> "vagasruby.wouerner.dev". */
    private static function normalize(string $host): string
    {
        $host = strtolower(trim(explode(',', $host)[0]));
        $host = preg_replace('#^https?://#', '', $host);
        return rtrim((string) preg_replace('/:\d+$/', '', (string) $host), '/.');
    }

    /**
     * Escolhe o site da requisição e liga a marca dele (Brand::use). Devolve o tenant, ou
     * null sem VAGAS_SITES (modo de um site: quem decide é VAGAS_TENANT).
     */
    public static function select(Request $request, ?string $spec = null): ?string
    {
        $map = self::map($spec);
        self::$all = $map;
        if (!$map) {
            self::$current = null;
            return null;
        }
        $host = self::normalize($request->header('host') ?? $request->host);
        if (!isset($map[$host])) {
            $host = array_key_first($map);
        }
        self::$current = ['host' => $host, 'tenant' => $map[$host], 'default' => $host === array_key_first($map)];
        Brand::use($map[$host]);
        return $map[$host];
    }

    /** Volta ao modo de um site (testes). */
    public static function reset(): void
    {
        self::$current = null;
        self::$all = [];
        Brand::use(null);
    }

    /**
     * Barra de abas no topo de todas as páginas, como as abas do navegador: um link para cada
     * site da família Vagas (na ordem de VAGAS_SITES), com a aba do site atual em destaque. A aba
     * traz só o ícone e o nome da linguagem: todos os sites são de vagas. É a
     * única parte compartilhada entre os sites. Vazia com menos de dois sites (modo de um site).
     * Entra depois do Brand::fill: os nomes das outras linguagens não podem virar a do site atual.
     */
    public static function tabs(): string
    {
        if (self::$current === null || count(self::$all) < 2) {
            return '';
        }
        $links = '';
        foreach (self::$all as $host => $tenant) {
            $brand = Brand::BRANDS[$tenant] ?? null;
            if ($brand === null) {
                continue;
            }
            $current = $host === self::$current['host'] ? ' aria-current="page"' : '';
            $links .= '<a href="https://' . htmlspecialchars($host) . '/"' . $current . '>'
                . '<img src="' . htmlspecialchars($brand['icon']) . '" alt="" width="16" height="16">'
                . htmlspecialchars($brand['lang']) . '</a>';
        }
        return <<<HTML
<nav id="site-tabs" aria-label="Sites de vagas por linguagem"><div>{$links}</div></nav>
<style>
  #site-tabs { display: block; margin: 0; padding: 0; background: var(--line); }
  #site-tabs > div { max-width: 920px; margin: 0 auto; padding: 6px 16px 0; display: flex; gap: 2px;
    overflow-x: auto; scrollbar-width: none; }
  #site-tabs > div::-webkit-scrollbar { display: none; }
  #site-tabs a { display: flex; align-items: center; gap: 7px; padding: 7px 14px 8px; white-space: nowrap;
    border-radius: 10px 10px 0 0; font-size: 13px; line-height: 1; font-weight: 400; color: var(--muted);
    text-decoration: none; background: color-mix(in srgb, var(--bg) 40%, transparent); }
  #site-tabs a:hover { color: var(--text); background: color-mix(in srgb, var(--bg) 70%, transparent); }
  #site-tabs a[aria-current] { color: var(--text); background: var(--bg); font-weight: 600; }
  #site-tabs a:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  #site-tabs img { width: 16px; height: 16px; flex: none; }
  @media (max-width: 480px) { #site-tabs a { padding: 7px 11px 8px; } }
</style>
HTML;
    }

    /** Endereço público do site atual ("https://vagasruby.wouerner.dev"), ou null sem VAGAS_SITES. */
    public static function url(): ?string
    {
        return self::$current === null ? null : 'https://' . self::$current['host'];
    }

    /** Variável de ambiente do site atual: NOME_TENANT; NOME só no site padrão (ou sem VAGAS_SITES). */
    public static function env(string $name): string
    {
        if (self::$current !== null) {
            $own = trim((string) getenv($name . '_' . strtoupper(self::$current['tenant'])));
            if ($own !== '' || !self::$current['default']) {
                return $own;
            }
        }
        return trim((string) getenv($name));
    }
}
