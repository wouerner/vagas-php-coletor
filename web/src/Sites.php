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
        Brand::use(null);
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
