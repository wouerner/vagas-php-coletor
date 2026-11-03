<?php

declare(strict_types=1);

namespace VagasPhp;

/**
 * Rajadas de vagas da mesma empresa (ex.: a BairesDev publica 16 vagas PHP em 3h30, uma
 * por cidade): na listagem viram um card só, que abre para mostrar as vagas. É só
 * apresentação: a base, a contagem, a paginação e a API crua não mudam.
 *
 * Regra: vagas da mesma empresa entram no mesmo grupo enquanto cada publicação estiver a
 * até GAP segundos da anterior da mesma empresa (encadeado: uma onda longa com intervalos
 * curtos continua num grupo só); um intervalo maior abre um grupo novo. Empresa: company_key
 * do coletor; sem ele, o nome normalizado (as duas chaves nunca se misturam). Issues do
 * GitHub (empresa vem de texto livre) e vagas sem empresa ou sem data ficam sozinhas.
 *
 * O grupo fica na posição da vaga mais recente dele; dentro, a ordem da lista. Igual a
 * bursts() de templates/index.html: mudou um, mude o outro.
 */
final class Bursts
{
    /** Maior intervalo entre publicações consecutivas da mesma empresa no mesmo grupo. */
    public const GAP = 12 * 3600;
    /** Títulos e cidades que o resumo do card mostra antes do "e mais N". */
    public const TITLES = 3;
    public const PLACES = 5;

    /** Chave da empresa para agrupar, ou null (não agrupa). */
    public static function key(array $job): ?string
    {
        if (($job['source'] ?? null) === 'github') {
            return null;
        }
        $key = trim((string) ($job['company_key'] ?? ''));
        if ($key !== '') {
            return "k:$key";
        }
        $name = trim((string) preg_replace('/\s+/u', ' ', Text::fold(trim((string) ($job['company'] ?? '')))));
        return $name !== '' ? "n:$name" : null;
    }

    /**
     * Chave opaca para o navegador agrupar (campo burst_key de /api/jobs?burst=1): não
     * expõe o company_key, que a API esconde.
     */
    public static function publicKey(array $job): ?string
    {
        $key = self::key($job);
        return $key === null ? null : substr(hash('sha256', $key), 0, 16);
    }

    /** Quando a vaga foi publicada (a mesma data que ordena a lista), ou null. */
    public static function time(array $job): ?int
    {
        return Dates::parse(($job['posted_at'] ?? null) ?: ($job['first_seen'] ?? null))?->getTimestamp();
    }

    /**
     * Separa a lista (mais recentes primeiro) em itens: uma vaga sozinha ou um grupo.
     *
     * @param list<array<string, mixed>> $jobs
     * @return list<list<array<string, mixed>>>
     */
    public static function group(array $jobs): array
    {
        $items = [];
        $open = [];  // chave -> [índice do grupo em $items, data da última vaga do grupo]
        foreach ($jobs as $job) {
            $key = self::key($job);
            $at = self::time($job);
            if ($key === null || $at === null) {
                $items[] = [$job];
                continue;
            }
            if (isset($open[$key]) && abs($open[$key][1] - $at) <= self::GAP) {
                $items[$open[$key][0]][] = $job;
                $open[$key][1] = $at;
            } else {
                $items[] = [$job];
                $open[$key] = [count($items) - 1, $at];
            }
        }
        return $items;
    }

    /** Cards da lista: vaga sozinha com Site::jobCard, grupo com card(). */
    public static function html(array $jobs, string $page = '/'): string
    {
        return implode('', array_map(fn ($item) => count($item) > 1 ? self::card($item, $page)
            : Site::jobCard($item[0], $page), self::group($jobs)));
    }

    /** "45 min", "3 h", "3 h 31 min". */
    public static function span(int $seconds): string
    {
        $m = intdiv(max(0, $seconds), 60);
        if ($m < 60) {
            return "$m min";
        }
        return intdiv($m, 60) . ' h' . ($m % 60 ? ' ' . ($m % 60) . ' min' : '');
    }

    /**
     * "6× Desenvolvedor PHP · 3× Backend" (mais comuns primeiro) e "e mais N" no fim.
     *
     * @param list<string> $values
     */
    public static function summary(array $values, int $max, bool $counts): string
    {
        $pairs = Text::mostCommon(array_values(array_filter(array_map('trim', $values), fn ($v) => $v !== '')));
        $shown = array_map(fn ($p) => $counts && $p[1] > 1 ? "{$p[1]}× {$p[0]}" : $p[0], array_slice($pairs, 0, $max));
        $rest = count($pairs) - count($shown);
        return implode(' · ', $shown) . ($rest > 0 ? " · e mais $rest" : '');
    }

    /** Card do grupo: empresa, quantas vagas, janela de publicação, resumo e as vagas. */
    public static function card(array $jobs, string $page = '/'): string
    {
        $e = Text::e(...);
        $newest = $jobs[0];
        $oldest = $jobs[count($jobs) - 1];
        $n = count($jobs);
        $a = Site::age(($newest['posted_at'] ?? null) ?: ($newest['first_seen'] ?? null));
        $first = Site::age(($oldest['posted_at'] ?? null) ?: ($oldest['first_seen'] ?? null));
        $company = trim((string) $newest['company']);
        $window = 'publicadas em ' . self::span((int) self::time($newest) - (int) self::time($oldest))
            . ($a && $first ? ', de ' . $first['at'] . ' a ' . $a['at'] . ' (Brasília)' : '');
        $titles = self::summary(array_map(fn ($j) => (string) ($j['title'] ?? ''), $jobs), self::TITLES, true);
        $places = self::summary(array_map(fn ($j) => (string) ($j['location'] ?? ''), $jobs), self::PLACES, false);
        $tags = '';
        foreach (array_unique(array_map(fn ($j) => (string) $j['source'], $jobs)) as $s) {
            $tags .= '<span class="tag src">' . $e(Site::SOURCE_NAMES[$s] ?? $s) . '</span>';
        }
        $age = $a ? "<span class=\"age\" title=\"Vaga mais recente {$a['label']}: publicada há {$a['text']}\">{$a['text']}</span>" : '';
        $band = $a ? " {$a['band']}" : '';
        $cards = implode('', array_map(fn ($j) => Site::jobCard($j, $page), $jobs));
        return "<li class=\"job burst$band\" data-id=\"burst-" . $e((string) $oldest['id']) . '"><div class="head"><h2>'
            . $e($company) . ' · ' . $n . ' vagas</h2>' . "$age</div><div class=\"meta\">" . $e($window) . '</div>'
            . ($titles !== '' ? '<div class="meta titles">' . $e($titles) . '</div>' : '')
            . ($places !== '' ? '<div class="meta places">' . $e($places) . '</div>' : '')
            . "<div class=\"tags\">$tags</div><details class=\"burst-list\"><summary>Ver as $n vagas</summary>"
            . "<ul class=\"burst-jobs\">$cards</ul></details></li>";
    }
}
