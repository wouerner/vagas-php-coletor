<?php

declare(strict_types=1);

namespace VagasPhp\Http;

final class Json
{
    /** JSON compacto, UTF-8 sem escapar acentos nem barras (como o JSONResponse do Starlette). */
    public static function encode(mixed $data): string
    {
        return json_encode(
            $data,
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR,
        );
    }
}
