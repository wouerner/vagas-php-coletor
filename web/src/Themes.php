<?php

declare(strict_types=1);

namespace VagasPhp;

/**
 * Páginas por tema (/vagas/laravel-remoto): uma por stack, modalidade e senioridade (da
 * taxonomia do filtro, que o coletor grava em site_meta) e as combinações abaixo, que têm
 * volume de vagas para valer uma página. Endereços estáveis: tema sem vaga aberta continua
 * existindo, com o aviso e os temas relacionados.
 */
final class Themes
{
    public const STACK_WORKPLACE = ['Laravel' => ['Remoto', 'Híbrido', 'Presencial'], 'Symfony' => ['Remoto'],
        'WordPress' => ['Remoto'], 'Magento' => ['Remoto'], 'CodeIgniter' => ['Remoto'], 'Drupal' => ['Remoto']];
    public const STACK_SENIORITY = ['Laravel' => ['Júnior', 'Pleno', 'Sênior']];
    public const SENIORITY_WORKPLACE = ['Júnior' => ['Remoto'], 'Pleno' => ['Remoto'], 'Sênior' => ['Remoto']];
    public const WORKPLACE_PLURAL = ['Remoto' => 'remotas', 'Híbrido' => 'híbridas', 'Presencial' => 'presenciais'];
    public const GROUPS = ['Por stack', 'Por modalidade', 'Por senioridade', 'Combinações'];

    /** @var array<string, array> temas por slug */
    public readonly array $themes;
    /** @var array<string, string> apelidos (/vagas/junior -> php-junior) */
    public readonly array $aliases;

    /** @param array{stacks?: list<string>, workplaces?: list<string>, seniorities?: list<string>}|null $taxonomy */
    public function __construct(?array $taxonomy)
    {
        $stacks = array_values(array_filter($taxonomy['stacks'] ?? [], fn ($s) => $s !== 'PHP'));
        $workplaces = $taxonomy['workplaces'] ?? [];
        $levels = $taxonomy['seniorities'] ?? [];
        $combos = [];
        foreach ($stacks as $s) {
            $combos[] = [0, $s, null, null];
        }
        foreach ($workplaces as $w) {
            $combos[] = [1, null, $w, null];
        }
        foreach ($levels as $lv) {
            $combos[] = [2, null, null, $lv];
        }
        foreach (self::STACK_WORKPLACE as $s => $ws) {
            foreach ($ws as $w) {
                $combos[] = [3, $s, $w, null];
            }
        }
        foreach (self::STACK_SENIORITY as $s => $lvs) {
            foreach ($lvs as $lv) {
                $combos[] = [3, $s, null, $lv];
            }
        }
        foreach (self::SENIORITY_WORKPLACE as $lv => $ws) {
            foreach ($ws as $w) {
                $combos[] = [3, null, $w, $lv];
            }
        }
        $themes = [];
        foreach ($combos as [$group, $stack, $workplace, $level]) {
            // Combinação com valor que o filtro não conhece mais: fica de fora.
            if (($stack && !in_array($stack, $stacks, true)) || ($workplace && !in_array($workplace, $workplaces, true))
                || ($level && !in_array($level, $levels, true))) {
                continue;
            }
            $parts = [$stack ? Text::slugify($stack) : ($level ? 'php' : null),
                $level ? Text::slugify($level) : null, $workplace ? Text::slugify($workplace) : null];
            $slug = implode('-', array_filter($parts));
            $themes[$slug] = ['slug' => $slug, 'path' => "/vagas/$slug", 'group' => self::GROUPS[$group],
                'name' => self::name($stack, $workplace, $level),
                'stack' => $stack, 'workplace' => $workplace, 'seniority' => $level];
        }
        $aliases = [];
        foreach ($levels as $level) {
            $aliases[Text::slugify($level)] = 'php-' . Text::slugify($level);
        }
        $this->themes = $themes;
        $this->aliases = $aliases;
    }

    /** "Vagas Laravel remotas", "Vagas PHP sênior remotas", "Vagas de estágio em PHP". */
    public static function name(?string $stack, ?string $workplace, ?string $seniority): string
    {
        $tech = $stack ?: 'PHP';
        if ($seniority === 'Estágio') {
            $name = "Vagas de estágio em $tech";
        } else {
            $name = implode(' ', array_filter(['Vagas', $tech, $seniority ? mb_strtolower($seniority) : null]));
        }
        if ($workplace) {
            $name .= ' ' . (self::WORKPLACE_PLURAL[$workplace] ?? mb_strtolower($workplace));
        }
        return $name;
    }

    public static function matches(array $theme, array $job): bool
    {
        return (!$theme['stack'] || in_array($theme['stack'], explode(',', $job['stack'] ?? ''), true))
            && (!$theme['workplace'] || ($job['workplace'] ?? null) === $theme['workplace'])
            && (!$theme['seniority'] || ($job['seniority'] ?? null) === $theme['seniority']);
    }

    /** @return list<string> "chave=valor" dos filtros do tema */
    private static function dims(array $theme): array
    {
        $out = [];
        foreach (['stack', 'workplace', 'seniority'] as $k) {
            if ($theme[$k]) {
                $out[] = "$k=" . $theme[$k];
            }
        }
        return $out;
    }

    /** @return array<string, int> vagas por slug */
    public function counts(array $jobs): array
    {
        $counts = [];
        foreach ($this->themes as $slug => $t) {
            foreach ($jobs as $j) {
                if (self::matches($t, $j)) {
                    $counts[$slug] = ($counts[$slug] ?? 0) + 1;
                }
            }
        }
        return $counts;
    }

    /**
     * Temas com vaga aberta mais gerais (Laravel para Laravel remotas), mais específicos e
     * vizinhos (mesmo tipo de filtro, um valor diferente: Symfony remotas).
     */
    public function related(array $theme, array $counts, int $limit = 16): array
    {
        $mine = self::dims($theme);
        $mineKeys = array_map(fn ($d) => explode('=', $d)[0], $mine);
        $near = [];
        foreach ($this->themes as $t) {
            if ($t['slug'] === $theme['slug'] || empty($counts[$t['slug']])) {
                continue;
            }
            $dims = self::dims($t);
            $common = count(array_intersect($dims, $mine));
            if (count($dims) < count($mine) && $common === count($dims)) {
                $rank = 0;
            } elseif (count($dims) > count($mine) && $common === count($mine)) {
                $rank = 1;
            } elseif (array_map(fn ($d) => explode('=', $d)[0], $dims) == $mineKeys && $common === count($mine) - 1) {
                $rank = 2;
            } else {
                continue;
            }
            $near[] = [$rank, $t];
        }
        usort($near, fn ($a, $b) => [$a[0], -$counts[$a[1]['slug']]] <=> [$b[0], -$counts[$b[1]['slug']]]);
        return array_map(fn ($rt) => $rt[1], array_slice($near, 0, $limit));
    }

    public static function links(array $themes, array $counts): string
    {
        $out = '';
        foreach ($themes as $t) {
            $n = $counts[$t['slug']] ?? 0;
            $out .= '<a href="' . $t['path'] . '"' . ($n ? '' : ' class=zero') . '>'
                . Text::e($t['name']) . ' <span class="n">' . $n . '</span></a>';
        }
        return $out;
    }

    public function allHtml(array $counts): string
    {
        $out = '';
        foreach (self::GROUPS as $group) {
            $themes = array_filter($this->themes, fn ($t) => $t['group'] === $group);
            $out .= "<section class=\"themes\"><h2>$group</h2><nav>" . self::links($themes, $counts) . '</nav></section>';
        }
        return $out;
    }

    /**
     * Temas de um filtro só (Laravel, Remoto, Sênior...), com `value` (o valor do filtro):
     * links nas tabelas e no llms.txt do /mercado-php.
     */
    public function topics(): array
    {
        $out = [];
        foreach ($this->themes as $t) {
            if ((int) (bool) $t['stack'] + (int) (bool) $t['workplace'] + (int) (bool) $t['seniority'] === 1) {
                $out[] = $t + ['value' => $t['stack'] ?: ($t['workplace'] ?: $t['seniority'])];
            }
        }
        return $out;
    }
}
