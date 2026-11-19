<?php

declare(strict_types=1);

namespace VagasPhp\Http;

/**
 * Rotas GET/POST (e HEAD para GET). Padrões com {nome} casam um trecho sem "/". Caminho com barra no
 * fim que existe sem ela redireciona (307), como no Starlette.
 */
final class Router
{
    /** @var list<array{list<string>, string, callable(Request): Response}> */
    private array $routes = [];

    /** @param callable(Request): Response $handler */
    public function get(string $pattern, callable $handler): void
    {
        $this->add(['GET'], $pattern, $handler);
    }

    /** @param callable(Request): Response $handler */
    public function post(string $pattern, callable $handler): void
    {
        $this->add(['POST'], $pattern, $handler);
    }

    /** @param list<string> $methods @param callable(Request): Response $handler */
    private function add(array $methods, string $pattern, callable $handler): void
    {
        $regex = '#^' . preg_replace('#\\\\\{(\w+)\\\\\}#', '(?P<$1>[^/]+)', preg_quote($pattern, '#')) . '$#';
        $this->routes[] = [$methods, $regex, $handler];
    }

    public function dispatch(Request $request): Response
    {
        $match = $this->match($request->method, $request->path);
        if ($match === null && $request->path !== '/' && str_ends_with($request->path, '/')) {
            $alt = rtrim($request->path, '/');
            if ($this->match($request->method, $alt) !== null) {
                $qs = http_build_query($request->query, '', '&', PHP_QUERY_RFC3986);
                return Response::redirect($alt . ($qs !== '' ? "?$qs" : ''), 307);
            }
        }
        if ($match === null) {
            return Response::text('Not Found', status: 404);
        }
        [$handler, $params] = $match;
        $request->params = $params;
        return $handler($request);
    }

    /** @return array{callable(Request): Response, array<string, string>}|null */
    private function match(string $method, string $path): ?array
    {
        foreach ($this->routes as [$methods, $regex, $handler]) {
            $ok = in_array($method, $methods, true) || ($method === 'HEAD' && in_array('GET', $methods, true));
            if ($ok && preg_match($regex, $path, $m)) {
                return [$handler, array_filter($m, 'is_string', ARRAY_FILTER_USE_KEY)];
            }
        }
        return null;
    }
}
