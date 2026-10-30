<?php

declare(strict_types=1);

namespace VagasPhp\Http;

/**
 * Rotas GET (e HEAD). Padrões com {nome} casam um trecho sem "/". Caminho com barra no
 * fim que existe sem ela redireciona (307), como no Starlette.
 */
final class Router
{
    /** @var list<array{string, string, callable(Request): Response}> */
    private array $routes = [];

    /** @param callable(Request): Response $handler */
    public function get(string $pattern, callable $handler): void
    {
        $regex = '#^' . preg_replace('#\\\\\{(\w+)\\\\\}#', '(?P<$1>[^/]+)', preg_quote($pattern, '#')) . '$#';
        $this->routes[] = [$pattern, $regex, $handler];
    }

    public function dispatch(Request $request): Response
    {
        $match = $this->match($request->path);
        if ($match === null && $request->path !== '/' && str_ends_with($request->path, '/')) {
            $alt = rtrim($request->path, '/');
            if ($this->match($alt) !== null) {
                $qs = http_build_query($request->query, '', '&', PHP_QUERY_RFC3986);
                return Response::redirect($alt . ($qs !== '' ? "?$qs" : ''), 307);
            }
        }
        if ($match === null) {
            return Response::text('Not Found', status: 404);
        }
        if (!in_array($request->method, ['GET', 'HEAD'], true)) {
            return new Response('Method Not Allowed', 405, ['Content-Type' => 'text/plain; charset=utf-8', 'Allow' => 'GET, HEAD']);
        }
        [$handler, $params] = $match;
        $request->params = $params;
        return $handler($request);
    }

    /** @return array{callable(Request): Response, array<string, string>}|null */
    private function match(string $path): ?array
    {
        foreach ($this->routes as [, $regex, $handler]) {
            if (preg_match($regex, $path, $m)) {
                return [$handler, array_filter($m, 'is_string', ARRAY_FILTER_USE_KEY)];
            }
        }
        return null;
    }
}
