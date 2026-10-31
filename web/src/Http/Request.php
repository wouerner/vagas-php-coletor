<?php

declare(strict_types=1);

namespace VagasPhp\Http;

/** Requisição HTTP: método, caminho, query string, cabeçalhos (nomes em minúsculas) e IP de quem conectou. */
final class Request
{
    /**
     * @param array<string, string> $query
     * @param array<string, string> $headers
     */
    public function __construct(
        public readonly string $method,
        public readonly string $path,
        public readonly array $query = [],
        public readonly array $headers = [],
        public readonly string $scheme = 'http',
        public readonly string $host = 'localhost',
        /** @var array<string, string> parâmetros do caminho (/vagas/{slug}) */
        public array $params = [],
        /** REMOTE_ADDR: atrás do proxy é o IP dele (o do visitante vem nos cabeçalhos) */
        public readonly string $ip = '',
    ) {
    }

    public static function fromGlobals(): self
    {
        $headers = [];
        foreach ($_SERVER as $key => $value) {
            if (str_starts_with($key, 'HTTP_')) {
                $headers[strtolower(str_replace('_', '-', substr($key, 5)))] = (string) $value;
            }
        }
        $uri = $_SERVER['REQUEST_URI'] ?? '/';
        $path = rawurldecode(parse_url($uri, PHP_URL_PATH) ?: '/');
        $https = ($_SERVER['HTTPS'] ?? '') !== '' && ($_SERVER['HTTPS'] ?? '') !== 'off';
        $host = $headers['host'] ?? ($_SERVER['SERVER_NAME'] ?? 'localhost');
        return new self(
            strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET'),
            $path,
            self::parseQuery((string) ($_SERVER['QUERY_STRING'] ?? '')),
            $headers,
            $https ? 'https' : 'http',
            $host,
            ip: (string) ($_SERVER['REMOTE_ADDR'] ?? ''),
        );
    }

    /**
     * Query string como no Starlette: o último valor de cada nome vale, sem a conversão
     * de "." e espaço em "_" que o $_GET do PHP faz.
     *
     * @return array<string, string>
     */
    public static function parseQuery(string $qs): array
    {
        $out = [];
        foreach (explode('&', $qs) as $pair) {
            if ($pair === '') {
                continue;
            }
            [$name, $value] = array_pad(explode('=', $pair, 2), 2, '');
            $out[urldecode($name)] = urldecode($value);
        }
        return $out;
    }

    public function get(string $name): ?string
    {
        return $this->query[$name] ?? null;
    }

    public function has(string $name): bool
    {
        return array_key_exists($name, $this->query);
    }

    public function header(string $name): ?string
    {
        return $this->headers[strtolower($name)] ?? null;
    }
}
