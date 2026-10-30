<?php

declare(strict_types=1);

namespace VagasPhp\Http;

final class Response
{
    /** @param array<string, string> $headers */
    public function __construct(
        public string $body = '',
        public int $status = 200,
        public array $headers = [],
    ) {
    }

    public static function html(string $html, int $status = 200): self
    {
        return new self($html, $status, ['Content-Type' => 'text/html; charset=utf-8']);
    }

    public static function json(mixed $data, int $status = 200): self
    {
        return new self(Json::encode($data), $status, ['Content-Type' => 'application/json']);
    }

    public static function text(string $text, string $type = 'text/plain; charset=utf-8', int $status = 200): self
    {
        return new self($text, $status, ['Content-Type' => $type]);
    }

    /** @param array<string, string> $headers */
    public static function redirect(string $url, int $status = 302, array $headers = []): self
    {
        return new self('', $status, ['Location' => $url] + $headers);
    }

    public function send(bool $head = false): void
    {
        http_response_code($this->status);
        foreach ($this->headers as $name => $value) {
            header("$name: $value");
        }
        if (!$head) {
            echo $this->body;
        }
    }
}
