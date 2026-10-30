<?php

declare(strict_types=1);

namespace VagasPhp;

use DateTimeImmutable;
use VagasPhp\Http\Request;
use VagasPhp\Http\Response;

/**
 * Página /mercado-php (mercado de trabalho PHP no Brasil em números) e /llms.txt (resumo
 * do site para assistentes de IA, formato llmstxt.org).
 *
 * Tudo renderizado no servidor, em frases com números e datas que buscadores e robôs de
 * IA possam citar ("Há 68 vagas PHP abertas no Brasil (publicadas nas últimas 72 horas),
 * de 40 empresas; 61% remotas."). Os números vêm de Repo::dashboard(), companies() e
 * recruiters(), com as mesmas regras do resto do site.
 */
final class Mercado
{
    public const PATH = '/mercado-php';
    public const WEEKS = 8;  // semanas na tabela de vagas novas por semana
    public const SOURCE_NAMES = ['linkedin' => 'Vagas do LinkedIn', 'gupy' => 'Gupy', 'post' => 'Publicações do LinkedIn',
        'github' => 'GitHub', 'remotar' => 'Remotar', 'programathor' => 'Programathor', 'catho' => 'Catho',
        'solides' => 'Sólides', 'inhire' => 'InHire', 'coodesh' => 'Coodesh', 'nerdin' => 'Nerdin',
        'recrutei' => 'Recrutei', 'upvagas' => 'UpVagas'];
    public const MISSING = 'Não informado';

    public function __construct(private readonly Site $site)
    {
    }

    /** "Laravel" -> "/vagas/laravel", "Remoto" -> "/vagas/remoto", "Sênior" -> "/vagas/php-senior". */
    private function topicPaths(): array
    {
        return array_column($this->site->themes()->topics(), 'path', 'value');
    }

    // --- dados ---------------------------------------------------------------------------

    /** Números da página. PDOException de tabela ausente passa para quem chama. */
    public function market(): array
    {
        $repo = $this->site->repo;
        $today = Dates::local(Dates::now())->setTime(0, 0);
        $weekday = (int) $today->format('N') - 1;
        $monday = $today->modify("-$weekday days");
        // Série diária desde a segunda-feira de WEEKS - 1 semanas atrás (a atual em andamento).
        $dash = $repo->dashboard(7 * (self::WEEKS - 1) + $weekday + 1);
        $weeks = [];
        for ($i = 0; $i < self::WEEKS; $i++) {
            $start = $monday->modify('-' . (7 * (self::WEEKS - 1 - $i)) . ' days');
            $jobs = 0;
            foreach ($dash['daily'] as $d) {
                $diff = (int) $start->diff(new DateTimeImmutable($d['day'], Dates::brasilia()))->format('%r%a');
                if ($diff >= 0 && $diff < 7) {
                    foreach ($d as $k => $n) {
                        if ($k !== 'day') {
                            $jobs += $n;
                        }
                    }
                }
            }
            $weeks[] = ['start' => $start, 'end' => $start->modify('+6 days'), 'jobs' => $jobs,
                'current' => $start == $monday];
        }
        $since = $dash['collecting_since'];
        $sinceDay = $since ? Dates::local(new DateTimeImmutable($since))->setTime(0, 0) : null;
        if ($sinceDay) {  // semanas inteiras antes da coleta começar não dizem nada
            $weeks = array_values(array_filter($weeks, fn ($w) => $w['end'] >= $sinceDay));
        }
        $oks = array_filter(array_column($dash['runs'], 'last_ok_at'));
        return $dash + [
            'weeks' => $weeks, 'since_day' => $sinceDay,
            'updated' => $oks ? max($oks) : Dates::utcIso(Dates::now()),
            'companies_list' => $repo->companies(Site::COMPANIES_DAYS, Site::COMPANIES_MIN),
            'companies_days' => Site::COMPANIES_DAYS, 'companies_min' => Site::COMPANIES_MIN,
            'recruiters_list' => $repo->recruiters(Site::RECRUITERS_DAYS, Site::recruitersMin(), Site::recruitersHide()),
            'recruiters_days' => Site::RECRUITERS_DAYS, 'recruiters_min' => Site::recruitersMin(),
            'sources_count' => count(self::SOURCE_NAMES),
        ];
    }

    // --- formatação ----------------------------------------------------------------------

    public static function brDate(DateTimeImmutable $day): string
    {
        return $day->format('d/m/Y');
    }

    /** "22/10/2026, 14h" (horário de Brasília). */
    public static function brWhen(string $iso): string
    {
        $dt = Dates::local(new DateTimeImmutable($iso));
        return self::brDate($dt) . ', ' . (int) $dt->format('G') . 'h';
    }

    public static function vagas(int $n, string $word = 'vaga'): string
    {
        return "$n $word" . ($n === 1 ? '' : 's');
    }

    /** Maiores primeiro, "Não informado" por último. */
    private static function sorted(array $pairs): array
    {
        $pairs = array_values(array_filter($pairs, fn ($p) => $p[1]));
        usort($pairs, fn ($a, $b) => [$a[0] === self::MISSING, -$a[1]] <=> [$b[0] === self::MISSING, -$b[1]]);
        return $pairs;
    }

    private static function label(string $name, array $paths): string
    {
        return isset($paths[$name]) ? "<a href=\"{$paths[$name]}\">" . Text::e($name) . '</a>' : Text::e($name);
    }

    /** Tabela nome | vagas | % do total. */
    private function table(array $pairs, int $total, string $head): string
    {
        $paths = $this->topicPaths();
        $rows = '';
        foreach ($pairs as [$k, $n]) {
            $rows .= '<tr><td>' . self::label($k, $paths) . "</td><td class=\"num\">$n</td>"
                . '<td class="num">' . Text::pct($n, $total) . '</td></tr>';
        }
        return '<table><thead><tr><th>' . Text::e($head) . '</th><th class="num">Vagas</th>'
            . "<th class=\"num\">%</th></tr></thead><tbody>$rows</tbody></table>";
    }

    private static function get(array $pairs, string $key): int
    {
        foreach ($pairs as [$k, $n]) {
            if ($k === $key) {
                return $n;
            }
        }
        return 0;
    }

    private static function empty(string $text): string
    {
        return '<p class="muted">' . Text::e($text) . '</p>';
    }

    // --- frases --------------------------------------------------------------------------

    /** A frase principal, em texto puro (página, description e llms.txt). */
    public static function headline(array $d): string
    {
        [$k, $total] = [$d['kpis'], $d['kpis']['open']];
        $text = 'Há ' . self::vagas($total) . ' PHP abertas no Brasil (publicadas nas últimas 72 horas)';
        if ($k['companies']) {
            $text .= ", de {$k['companies']} empresa" . ($k['companies'] === 1 ? '' : 's');
        }
        if ($total) {
            $text .= '; ' . Text::pct($k['remote'], $total) . ' remotas';
        }
        return $text . '.';
    }

    /** HTML (escapado) de cada marca <!--ssr:...--> de templates/mercado.html. */
    public function sections(array $d): array
    {
        $e = Text::e(...);
        [$k, $total] = [$d['kpis'], $d['kpis']['open']];
        $when = self::brWhen($d['updated']);
        $out = ['updated' => 'Atualizado em <time datetime="' . $e($d['updated']) . '">' . $e($when) . '</time>.'];

        $resumo = [$e(self::headline($d)) . ' Dados de ' . $e($when) . ' (horário de Brasília).'];
        $resumo[] = 'Nas últimas 24 horas foram publicadas ' . self::vagas($k['new_24h'], 'vaga') . ' PHP novas; '
            . "nas 24 horas anteriores, {$k['prev_24h']}.";
        // Semanas completas: nem a atual nem a do começo da coleta (só parte dela foi coletada).
        $full = array_values(array_filter($d['weeks'], fn ($w) => !$w['current']
            && !($d['since_day'] && $w['start'] < $d['since_day'])));
        if ($full) {
            $w = end($full);
            $resumo[] = 'Na semana de ' . self::brDate($w['start']) . ' a ' . self::brDate($w['end']) . ' foram publicadas '
                . self::vagas($w['jobs']) . ' PHP novas.';
        }
        $out['resumo'] = implode('', array_map(fn ($p) => "<p>$p</p>", $resumo));

        if ($d['weeks']) {
            $rows = '';
            foreach ($d['weeks'] as $w) {
                $label = $w['start']->format('d/m') . ' a ' . $w['end']->format('d/m/Y');
                $notes = [];
                if ($w['current']) {
                    $notes[] = 'em andamento';
                }
                if ($d['since_day'] && $w['start'] < $d['since_day'] && $d['since_day'] <= $w['end']) {
                    $notes[] = 'coleta começou em ' . $d['since_day']->format('d/m');
                }
                if ($notes) {
                    $label .= ' (' . implode(', ', $notes) . ')';
                }
                $rows .= '<tr><td>' . $e($label) . "</td><td class=\"num\">{$w['jobs']}</td></tr>";
            }
            $text = '';
            if (count($full) >= 2) {
                [$a, $b] = array_slice($full, -2);
                $text = '<p>Na semana de ' . self::brDate($b['start']) . ' a ' . self::brDate($b['end']) . ' foram '
                    . 'publicadas ' . self::vagas($b['jobs']) . " PHP novas; na semana anterior, {$a['jobs']}.";
                $avg = array_sum(array_column($full, 'jobs')) / count($full);
                $text .= ' Média das últimas ' . count($full) . ' semanas completas: '
                    . Text::round($avg) . ' vagas por semana.</p>';
            }
            $out['semanas'] = $text . '<table><thead><tr><th>Semana (segunda a domingo)</th>'
                . "<th class=\"num\">Vagas novas</th></tr></thead><tbody>$rows"
                . '</tbody></table><p class="muted">Pela data de publicação, incluindo '
                . 'vagas que já saíram do ar.</p>';
        } else {
            $out['semanas'] = self::empty('Ainda não há semanas de coleta.');
        }

        if (!$total) {
            foreach (['modalidade', 'contrato', 'senioridade', 'stacks'] as $key) {
                $out[$key] = self::empty('Nenhuma vaga aberta nas últimas 72 horas.');
            }
        } else {
            $base = 'Das ' . self::vagas($total) . ' PHP abertas nas últimas 72 horas';
            $wp = $d['workplace'];
            $parts = [];
            foreach ([['Remoto', 'remotas'], ['Híbrido', 'híbridas'], ['Presencial', 'presenciais']] as [$w, $word]) {
                $parts[] = self::get($wp, $w) . ' (' . Text::pct(self::get($wp, $w), $total) . ") são $word";
            }
            $text = "$base, " . Text::joinAnd($parts);
            if ($miss = self::get($wp, self::MISSING)) {
                $text .= "; $miss não informa" . ($miss === 1 ? '' : 'm') . ' a modalidade';
            }
            $out['modalidade'] = '<p>' . $e($text) . '.</p>' . $this->table(self::sorted($wp), $total, 'Modalidade');

            $ct = $d['contract'];
            $informed = $total - self::get($ct, self::MISSING);
            if ($informed) {
                $text = 'Entre as vagas PHP abertas que informam o regime de contratação '
                    . "($informed de $total), " . Text::pct(self::get($ct, 'CLT'), $informed) . ' são CLT e '
                    . Text::pct(self::get($ct, 'PJ'), $informed) . ' são PJ';
                if (self::get($ct, 'Freelance')) {
                    $text .= '; ' . Text::pct(self::get($ct, 'Freelance'), $informed) . ' são freelance';
                }
                $text .= '. ' . Text::pct($total - $informed, $total) . ' das vagas não dizem o regime.';
            } else {
                $text = 'Nenhuma das vagas abertas informa o regime de contratação.';
            }
            $out['contrato'] = '<p>' . $e($text) . '</p>' . $this->table(self::sorted($ct), $total, 'Contratação');

            $sen = array_values(array_filter(self::sorted($d['seniority']), fn ($p) => $p[0] !== self::MISSING));
            if ($sen) {
                $text = 'A senioridade mais pedida nas vagas PHP abertas é ' . mb_strtolower($sen[0][0])
                    . ' (' . Text::pct($sen[0][1], $total) . ' das vagas)';
                if (count($sen) > 1) {
                    $text .= ', seguida de ' . Text::joinAnd(array_map(
                        fn ($p) => mb_strtolower($p[0]) . ' (' . Text::pct($p[1], $total) . ')', array_slice($sen, 1, 2)));
                }
                $text .= '.';
            } else {
                $text = 'As vagas abertas não informam a senioridade.';
            }
            $out['senioridade'] = '<p>' . $e($text) . '</p>' . $this->table(self::sorted($d['seniority']), $total, 'Senioridade');

            $stacks = $d['stack'];
            if ($stacks) {
                $items = [];
                foreach (array_slice($stacks, 0, 3) as $i => [$s, $n]) {
                    $items[] = $i === 0 ? "$s aparece em " . Text::pct($n, $total) : "$s em " . Text::pct($n, $total);
                }
                $text = 'Entre as vagas PHP abertas, ' . Text::joinAnd($items) . '.';
                $out['stacks'] = '<p>' . $e($text) . '</p>' . $this->table($stacks, $total, 'Framework / plataforma')
                    . '<p class="muted">Uma vaga pode citar mais de uma; as demais '
                    . 'pedem PHP sem framework citado.</p>';
            } else {
                $out['stacks'] = self::empty('As vagas abertas não citam frameworks além do PHP.');
            }
        }

        // Empresas
        [$cs, $cdays] = [$d['companies_list'], $d['companies_days']];
        if ($cs) {
            $top = array_slice($cs, 0, 10);
            $text = "Nos últimos $cdays dias, a empresa que mais anunciou vagas PHP foi "
                . "{$top[0]['name']} (" . self::vagas($top[0]['jobs']) . ')';
            if (count($top) > 1) {
                $text .= ', seguida de ' . Text::joinAnd(array_map(fn ($c) => "{$c['name']} ({$c['jobs']})", array_slice($top, 1, 2)));
            }
            $items = '';
            foreach ($top as $c) {
                $items .= '<li>' . $e($c['name']) . ': ' . self::vagas($c['jobs'])
                    . ($c['stack'] ? ' · ' . $e(implode(', ', array_slice($c['stack'], 0, 3))) : '') . '</li>';
            }
            $out['empresas'] = '<p>' . $e($text) . ".</p><ol>$items</ol>"
                . '<p><a href="/empresas">Ver todas as ' . count($cs) . ' empresas com '
                . "{$d['companies_min']} ou mais vagas</a></p>";
        } else {
            $out['empresas'] = self::empty("Ainda não há empresas com {$d['companies_min']} ou mais vagas nos últimos $cdays dias.")
                . '<p><a href="/empresas">Página de empresas</a></p>';
        }

        // Recrutadores
        [$rs, $rdays] = [$d['recruiters_list'], $d['recruiters_days']];
        if ($rs) {
            $items = '';
            foreach (array_slice($rs, 0, 5) as $r) {
                $items .= '<li>' . $e($r['name'] ?: 'Sem nome') . ': ' . self::vagas($r['jobs']) . '</li>';
            }
            $out['recrutadores'] = '<p>' . count($rs) . ' tech recruiter' . (count($rs) === 1 ? '' : 's') . ' '
                . "publicaram {$d['recruiters_min']} ou mais vagas PHP no LinkedIn nos "
                . "últimos $rdays dias. Os que mais publicaram:</p><ol>$items</ol>"
                . '<p><a href="/recrutadores">Ver todos os recrutadores</a></p>';
        } else {
            $out['recrutadores'] = self::empty("Ainda não há tech recruiters com {$d['recruiters_min']} ou mais "
                . "vagas PHP publicadas no LinkedIn nos últimos $rdays dias.")
                . '<p><a href="/recrutadores">Página de recrutadores</a></p>';
        }

        // Fontes
        $bySource = $d['by_source'];
        usort($bySource, fn ($a, $b) => $b[1] <=> $a[1]);
        $src = [];
        foreach ($bySource as [$s, $n]) {
            if ($n) {
                $src[] = [self::SOURCE_NAMES[$s] ?? $s, $n];
            }
        }
        if ($src && $total) {
            $text = 'As vagas abertas vêm de ' . count($src) . " das {$d['sources_count']} fontes coletadas; "
                . "a maior é {$src[0][0]}, com " . Text::pct($src[0][1], $total) . '.';
            $out['fontes'] = '<p>' . $e($text) . '</p>' . $this->table($src, $total, 'Fonte');
        } else {
            $out['fontes'] = self::empty('Nenhuma vaga aberta nas últimas 72 horas.');
        }
        $out['fontes'] .= '<p class="muted">Fontes coletadas: ' . $e(Text::joinAnd(array_values(self::SOURCE_NAMES))) . '.</p>';

        $topics = $this->site->themes()->topics();
        $out['temas'] = '';
        foreach (array_unique(array_column($topics, 'group')) as $group) {
            $out['temas'] .= '<p>' . $e($group) . ':</p><div class="topics">';
            foreach ($topics as $t) {
                if ($t['group'] === $group) {
                    $out['temas'] .= '<a href="' . $e($t['path']) . '">' . $e($t['value']) . '</a>';
                }
            }
            $out['temas'] .= '</div>';
        }

        $since = $d['since_day'] ? 'desde ' . self::brDate($d['since_day']) : 'desde o início da coleta';
        $out['metodologia'] = '<ul>'
            . "<li>Vagas coletadas várias vezes ao dia de {$d['sources_count']} fontes públicas "
            . '(portais de vagas, publicações do LinkedIn e repositórios de vagas no GitHub), ' . $e($since) . '.</li>'
            . '<li>Entram só vagas de engenharia de software com PHP, segundo as '
            . '<a href="/regras">regras de filtro do site</a>; o que não é vaga é descartado à mão.</li>'
            . '<li>A mesma vaga anunciada várias vezes (por cidade, por exemplo) conta uma vez.</li>'
            . '<li>Vagas abertas: publicadas nas últimas ' . Text::round($d['max_age_hours']) . ' horas e ainda no ar. '
            . 'Modalidade, contratação, senioridade e stack saem do texto da vaga; quando a vaga não '
            . 'diz, conta como não informado.</li>'
            . '<li>Os números são do que o site coleta, não do mercado inteiro: servem para comparar '
            . 'proporções e tendências.</li>'
            . '<li>Última coleta usada: ' . $e($when) . ' (horário de Brasília). O código do site é '
            . 'aberto.</li>'
            . '</ul>';
        return $out;
    }

    public static function description(array $d): string
    {
        $text = self::headline($d);
        $sen = array_values(array_filter(self::sorted($d['seniority']), fn ($p) => $p[0] !== self::MISSING));
        if ($d['stack'] && $d['kpis']['open']) {
            $text .= " {$d['stack'][0][0]} em " . Text::pct($d['stack'][0][1], $d['kpis']['open']) . '.';
        }
        if ($sen) {
            $text .= ' Senioridade mais pedida: ' . mb_strtolower($sen[0][0]) . '.';
        }
        return $text . ' Atualizado em ' . self::brWhen($d['updated']) . '.';
    }

    public static function jsonld(Request $request, array $d): array
    {
        $base = Seo::siteUrl($request);
        $site = ['@type' => 'Organization', 'name' => Seo::SITE_NAME, 'url' => $base . '/'];
        $dataset = [
            '@context' => 'https://schema.org', '@type' => 'Dataset',
            'name' => 'Vagas de emprego PHP no Brasil',
            'description' => 'Vagas de engenharia de software com PHP (Laravel, Symfony, WordPress e '
                . 'outros) anunciadas no Brasil, coletadas várias vezes ao dia de portais de '
                . 'vagas, publicações do LinkedIn e repositórios do GitHub, com modalidade '
                . '(remoto, híbrido, presencial), contratação (CLT, PJ), senioridade e stack. '
                . self::headline($d),
            'url' => $base . self::PATH, 'inLanguage' => 'pt-BR', 'isAccessibleForFree' => true,
            'creator' => $site, 'publisher' => $site,
            'dateModified' => $d['updated'],
            'spatialCoverage' => ['@type' => 'Place', 'name' => 'Brasil'],
            'keywords' => ['vagas PHP', 'mercado de trabalho PHP', 'Laravel', 'Symfony', 'WordPress',
                'vagas remotas', 'desenvolvedor PHP', 'Brasil'],
            'variableMeasured' => ['vagas abertas', 'vagas novas por semana', 'modalidade',
                'regime de contratação', 'senioridade', 'stack', 'empresa', 'fonte'],
            'distribution' => [
                ['@type' => 'DataDownload', 'encodingFormat' => 'application/json',
                    'contentUrl' => $base . '/api/dashboard', 'name' => 'Números do mercado'],
                ['@type' => 'DataDownload', 'encodingFormat' => 'application/json',
                    'contentUrl' => $base . '/api/jobs', 'name' => 'Vagas abertas'],
                ['@type' => 'DataDownload', 'encodingFormat' => 'application/json',
                    'contentUrl' => $base . '/api/companies', 'name' => 'Empresas que mais anunciam'],
            ],
        ];
        if ($d['since_day']) {
            $dataset['temporalCoverage'] = $d['since_day']->format('Y-m-d') . '/..';
        }
        return [Seo::breadcrumbs($request, ['Vagas PHP', '/'], ['Mercado de trabalho PHP', self::PATH]), $dataset];
    }

    // --- rotas ---------------------------------------------------------------------------

    public function page(Request $request): Response
    {
        $title = 'Mercado de trabalho PHP no Brasil';
        $d = Site::safe(fn () => $this->market(), null);
        if ($d === null) {  // tabelas ainda não criadas pelo coletor
            $html = Seo::render($request, 'mercado.html', $title, 'Números do mercado de trabalho PHP no Brasil.',
                self::PATH, ['resumo' => self::empty('Base ainda vazia: volte depois da primeira coleta.')], noindex: true);
            return Response::html($html, 503);
        }
        return Response::html(Seo::render($request, 'mercado.html', "$title · " . Seo::SITE_NAME,
            self::description($d), self::PATH, $this->sections($d), self::jsonld($request, $d)));
    }

    public function llmsText(Request $request): string
    {
        $base = Seo::siteUrl($request);
        $lines = ['# ' . Seo::SITE_NAME, '',
            '> Vagas de emprego para devs PHP no Brasil (Laravel, Symfony, WordPress...), '
            . 'coletadas várias vezes ao dia de portais de vagas, do LinkedIn e do GitHub.', ''];
        $d = Site::safe(fn () => $this->market(), null);
        if ($d) {
            $k = $d['kpis'];
            $text = self::headline($d) . ' Nas últimas 24 horas foram publicadas ' . self::vagas($k['new_24h']) . ' novas.';
            if ($d['stack'] && $k['open']) {
                $text .= ' Stacks mais pedidas: '
                    . Text::joinAnd(array_map(fn ($p) => "{$p[0]} (" . Text::pct($p[1], $k['open']) . ')', array_slice($d['stack'], 0, 3))) . '.';
            }
            $since = $d['since_day'] ? ' Coleta desde ' . self::brDate($d['since_day']) . '.' : '';
            $lines[] = "$text Dados de " . self::brWhen($d['updated']) . " (horário de Brasília).$since "
                . "Os números são do que o site coleta de {$d['sources_count']} fontes, não do "
                . 'mercado inteiro.';
            $lines[] = '';
        }
        array_push($lines,
            '## Páginas', '',
            "- [Vagas PHP abertas]($base/): vagas PHP publicadas nas últimas 72 horas, com filtros",
            "- [Mercado de trabalho PHP no Brasil]($base" . self::PATH . '): números atuais: vagas abertas, '
            . 'vagas por semana, remoto x presencial, CLT x PJ, senioridade, stacks e empresas',
            "- [Empresas]($base/empresas): empresas que mais anunciaram vagas PHP nos últimos 90 dias",
            "- [Recrutadores]($base/recrutadores): tech recruiters que mais publicam vagas PHP no LinkedIn",
            "- [Regras]($base/regras): como o site decide o que é vaga PHP",
            "- [Dashboard]($base/dashboard): gráficos das vagas por fonte e por dia, e estado das coletas",
            '', '## Vagas por tema', '',
        );
        foreach ($this->site->themes()->topics() as $t) {
            $lines[] = "- [{$t['name']}]($base{$t['path']}): vagas abertas nas últimas 72 horas";
        }
        array_push($lines,
            '', '## API JSON pública', '',
            "- [$base/api/jobs]($base/api/jobs): vagas abertas (últimas 72 h). Parâmetros: q (busca), "
            . 'source (linkedin, gupy, post, github...), workplace (Remoto, Híbrido, Presencial), '
            . 'seniority (Estágio, Júnior, Pleno, Sênior, Especialista), stack (Laravel, Symfony...), '
            . 'hours (1-72), include_closed (1), limit (1-200), offset',
            "- [$base/api/companies]($base/api/companies): empresas com 2 ou mais vagas PHP nos últimos 90 dias",
            "- [$base/api/recruiters]($base/api/recruiters): tech recruiters com vagas PHP nos últimos 90 dias",
            "- [$base/api/dashboard]($base/api/dashboard): números do mercado (vagas abertas, modalidade, "
            . 'contratação, senioridade, stacks, fontes) e série diária; days (3-90) muda o período da série',
            '',
        );
        return implode("\n", $lines);
    }

    public function llmsTxt(Request $request): Response
    {
        return Response::text($this->llmsText($request));
    }
}
