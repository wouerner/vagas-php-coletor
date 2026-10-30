<?php

declare(strict_types=1);

namespace VagasPhp;

/** Formatação de texto e HTML usada pelas páginas. */
final class Text
{
    /** Escapa para HTML (texto e atributos), com aspas simples como &#x27;. */
    public static function e(?string $s): string
    {
        return strtr((string) $s, ['&' => '&amp;', '<' => '&lt;', '>' => '&gt;', '"' => '&quot;', "'" => '&#x27;']);
    }

    /** "1 vaga" / "3 vagas". */
    public static function plural(int $n, string $one, string $many): string
    {
        return $n . ' ' . ($n === 1 ? $one : $many);
    }

    /** 12345 -> "12.345". */
    public static function fmt(int $n): string
    {
        return number_format($n, 0, ',', '.');
    }

    /** ["a", "b", "c"] -> "a, b e c". */
    public static function joinAnd(array $items): string
    {
        $items = array_values($items);
        if (count($items) === 1) {
            return $items[0];
        }
        return implode(', ', array_slice($items, 0, -1)) . ' e ' . $items[count($items) - 1];
    }

    /** Sem acentos e em minúsculas (busca da página /empresas). */
    public static function fold(string $text): string
    {
        $d = \Normalizer::normalize($text, \Normalizer::FORM_D);
        return mb_strtolower(preg_replace('/\p{Mn}/u', '', $d === false ? $text : $d));
    }

    /** "Desenvolvedor(a) PHP Sênior" -> "desenvolvedor-a-php-senior". */
    public static function slugify(?string $text, int $limit = 70): string
    {
        $t = \Normalizer::normalize($text ?? '', \Normalizer::FORM_KD);
        $t = strtolower(preg_replace('/[^\x00-\x7F]/', '', $t === false ? '' : $t));
        $t = trim(preg_replace('/[^a-z0-9]+/', '-', $t), '-');
        $t = rtrim(substr($t, 0, $limit), '-');
        return $t !== '' ? $t : 'vaga';
    }

    /** Primeira letra em minúscula ("Vagas Laravel" -> "vagas Laravel"). */
    public static function lcfirst(string $s): string
    {
        return mb_strtolower(mb_substr($s, 0, 1)) . mb_substr($s, 1);
    }

    /** Arredonda a metade para o par, como o round() do Python (62,5 -> 62). */
    public static function round(float $x): int
    {
        return (int) round($x, 0, PHP_ROUND_HALF_EVEN);
    }

    /** "62%" (0% sem total). */
    public static function pct(int $n, int $total): string
    {
        return $total ? self::round(100 * $n / $total) . '%' : '0%';
    }

    /** Query string como o urlencode() do Python (espaço vira "+", "~" fica). */
    public static function query(array $params): string
    {
        return str_replace('%7E', '~', http_build_query($params, '', '&', PHP_QUERY_RFC1738));
    }

    /** URL só se for http(s). */
    public static function safeUrl(?string $url): ?string
    {
        return $url !== null && $url !== '' && preg_match('#^https?://#i', $url) ? $url : null;
    }

    /**
     * Contagem por valor, maiores primeiro e, no empate, na ordem em que apareceram
     * (Counter.most_common do Python).
     *
     * @param iterable<string> $values
     * @return list<array{string, int}>
     */
    public static function mostCommon(iterable $values, ?int $n = null): array
    {
        $count = [];
        foreach ($values as $v) {
            $count[$v] = ($count[$v] ?? 0) + 1;
        }
        return self::topPairs($count, $n);
    }

    /**
     * @param array<string|int, int> $count
     * @return list<array{string, int}>
     */
    public static function topPairs(array $count, ?int $n = null): array
    {
        $pairs = [];
        foreach ($count as $k => $c) {
            $pairs[] = [(string) $k, $c];
        }
        usort($pairs, fn ($a, $b) => $b[1] <=> $a[1]);
        return $n === null ? $pairs : array_slice($pairs, 0, $n);
    }

    /** "PHP,Laravel" -> ["PHP", "Laravel"], sem vazios. @return list<string> */
    public static function stacks(?string $stack): array
    {
        return array_values(array_filter(explode(',', $stack ?? ''), fn ($s) => $s !== ''));
    }
}
