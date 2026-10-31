<?php

declare(strict_types=1);

namespace VagasPhp;

use DateTimeImmutable;
use VagasPhp\Http\Request;
use VagasPhp\Http\Response;

/**
 * Página de cada vaga de portal (/vaga/<seq>-<título>), renderizada no servidor para
 * buscadores e robôs de IA, com JSON-LD JobPosting para o Google for Jobs.
 *
 * Regras:
 * - seq inexistente, post do LinkedIn, vaga recusada pelo filtro ou descartada à mão: 404.
 * - título no endereço diferente do atual: 301 para o endereço de Seo::jobPath().
 * - a mesma vaga anunciada de novo (DEDUP: título + empresa + fonte): 301 para a mais recente.
 * - aberta (publicada há até maxAgeHours e sem closed_at): página completa com JobPosting.
 * - encerrada: 200 com noindex, sem JobPosting (o Google pede tirar o markup de vagas
 *   expiradas), aviso e links para vagas parecidas abertas.
 *
 * O JobPosting só sai com empresa conhecida (hiringOrganization é obrigatório): sem
 * empresa, empresa que não diz quem contrata (company_key nulo) ou issue do GitHub (o
 * campo empresa vem de texto livre da issue), a página continua, sem o markup.
 */
final class Vaga
{
    public const SOURCE_NAMES = ['linkedin' => 'LinkedIn', 'gupy' => 'Gupy', 'github' => 'GitHub', 'inhire' => 'InHire',
        'solides' => 'Sólides', 'catho' => 'Catho', 'remotar' => 'Remotar', 'programathor' => 'Programathor',
        'coodesh' => 'Coodesh', 'nerdin' => 'Nerdin', 'recrutei' => 'Recrutei', 'upvagas' => 'UpVagas'];
    public const EMPLOYMENT_TYPE = ['CLT' => 'FULL_TIME', 'PJ' => 'CONTRACTOR', 'Freelance' => 'CONTRACTOR'];
    public const UF = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB',
        'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];
    public const STATES = ['acre', 'alagoas', 'amapá', 'amazonas', 'bahia', 'ceará', 'distrito federal',
        'espírito santo', 'goiás', 'maranhão', 'mato grosso', 'mato grosso do sul', 'minas gerais', 'pará',
        'paraíba', 'paraná', 'pernambuco', 'piauí', 'rio de janeiro', 'rio grande do norte', 'rio grande do sul',
        'rondônia', 'roraima', 'santa catarina', 'são paulo', 'sergipe', 'tocantins'];
    public const CAPITAL_STATES = ['são paulo', 'rio de janeiro'];
    public const COUNTRY = ['brasil', 'brazil', 'br'];
    public const NO_PLACE = ['brasil', 'brazil', 'br', 'remoto', 'remote', 'home office', 'anywhere'];
    /**
     * Salário só vai para o JSON-LD no formato que os coletores gravam ("R$ 5.000",
     * "R$ 4.001 a R$ 5.000", "US$ 7.083 a US$ 10.417 por mês", "... por ano", "... por hora")
     * e com valores coerentes com o período. Sem período, só reais, tomados como salário
     * mensal; dólar sem período fica de fora.
     */
    public const SALARY = '/^(R\$|US\$) ?(\d{1,3}(?:\.\d{3})*)(?: a (R\$|US\$) ?(\d{1,3}(?:\.\d{3})*))?(?: por (m[eê]s|ano|hora))?$/u';
    public const CURRENCY = ['R$' => 'BRL', 'US$' => 'USD'];
    public const PERIOD = ['mês' => 'MONTH', 'mes' => 'MONTH', 'ano' => 'YEAR', 'hora' => 'HOUR'];
    public const SALARY_RANGE = ['MONTH' => [500, 100_000], 'YEAR' => [5_000, 2_000_000], 'HOUR' => [5, 2_000]];
    public const SIMILAR = 6;

    public function __construct(private readonly Site $site)
    {
    }

    // --- dados da vaga ---------------------------------------------------------------

    public static function posted(array $job): string
    {
        return $job['posted_at'] ?: $job['first_seen'];
    }

    public static function isOpen(array $job): bool
    {
        return empty($job['closed_at']) && strcmp(self::posted($job), Dates::cutoff()) >= 0;
    }

    /** Tema principal [nome, caminho]: a primeira stack além de PHP, ou PHP (/vagas). */
    public static function topic(array $job): array
    {
        $other = array_values(array_filter(Text::stacks($job['stack'] ?? null), fn ($s) => $s !== 'PHP'));
        return $other ? [$other[0], self::topicPath($other[0])] : ['PHP', '/vagas'];
    }

    public static function topicPath(string $name): string
    {
        return $name === 'PHP' ? '/vagas' : '/vagas/' . Text::slugify($name);
    }

    /** Empresa que contrata, para o hiringOrganization; null quando não dá para afirmar. */
    public static function employer(array $job): ?string
    {
        $name = trim($job['company'] ?? '');
        if (($job['source'] ?? null) === 'github' || empty($job['company_key'])) {
            return null;
        }
        return $name;
    }

    private static function lower(string $s): string
    {
        return mb_strtolower($s);
    }

    /**
     * PostalAddress a partir do texto de local ("São Paulo, SP", "Curitiba, Paraná, Brasil",
     * "Brasília - DF", "São Paulo e Região"). O local das issues do GitHub é texto livre:
     * fica só o país.
     */
    public static function address(array $job): array
    {
        $out = ['@type' => 'PostalAddress'];
        $text = rtrim(trim($job['location'] ?? ''), '.');
        if (($job['source'] ?? null) !== 'github' && $text !== '' && !str_contains($text, '/')) {
            $parts = array_values(array_filter(array_map('trim', preg_split('/,| - /u', $text)), fn ($p) => $p !== ''));
            while ($parts && in_array(self::lower(end($parts)), self::COUNTRY, true)) {
                array_pop($parts);
            }
            $parts = array_map(fn ($p) => preg_replace('/\s+e regi[aã]o$/iu', '', $p), $parts);
            $isRegion = fn ($p) => in_array(mb_strtoupper($p), self::UF, true) || in_array(self::lower($p), self::STATES, true);
            $region = null;
            foreach (array_slice($parts, 1) as $p) {
                if ($isRegion($p)) {
                    $region = $p;
                    break;
                }
            }
            if ($region !== null) {
                $out['addressRegion'] = mb_strlen($region) === 2 ? mb_strtoupper($region) : $region;
            }
            $first = $parts && !in_array(self::lower($parts[0]), self::NO_PLACE, true) ? $parts[0] : null;
            // "Rio Grande do Sul - RS" e "Minas Gerais" são só o estado; São Paulo e Rio de
            // Janeiro também são cidades.
            if ($first !== null && $isRegion($first) && !in_array(self::lower($first), self::CAPITAL_STATES, true)) {
                $out['addressRegion'] ??= $first;
            } elseif ($first !== null && $first !== '') {
                $out['addressLocality'] = $first;
            }
        }
        $out['addressCountry'] = 'BR';
        return $out;
    }

    public static function salary(array $job): ?array
    {
        if (!preg_match(self::SALARY, trim($job['salary'] ?? ''), $m)) {
            return null;
        }
        $m = array_pad($m, 6, '');
        if ($m[3] !== '' && $m[3] !== $m[1]) {
            return null;
        }
        $currency = self::CURRENCY[$m[1]];
        if ($m[5] === '' && $currency !== 'BRL') {
            return null;
        }
        $unit = $m[5] !== '' ? self::PERIOD[self::lower($m[5])] : 'MONTH';
        $low = (int) str_replace('.', '', $m[2]);
        $high = $m[4] !== '' ? (int) str_replace('.', '', $m[4]) : null;
        [$floor, $ceiling] = self::SALARY_RANGE[$unit];
        foreach ([$low, $high ?? $low] as $v) {
            if ($v < $floor || $v > $ceiling) {
                return null;
            }
        }
        if ($high && $high < $low) {
            return null;
        }
        $value = ['@type' => 'QuantitativeValue', 'unitText' => $unit];
        if ($high && $high !== $low) {
            $value += ['minValue' => $low, 'maxValue' => $high];
        } else {
            $value['value'] = $low;
        }
        return ['@type' => 'MonetaryAmount', 'currency' => $currency, 'value' => $value];
    }

    /** Uma linha já escapada com negrito e links do Markdown em HTML. */
    private static function inline(string $line): string
    {
        $line = preg_replace_callback('/\[([^\]]+)\]\(((?:https?:\/\/|mailto:)[^)\s]+)\)/u', function ($m) {
            if (str_starts_with($m[2], 'mailto:')) {
                return $m[1];
            }
            return "<a href=\"{$m[2]}\" rel=\"nofollow noopener\" target=\"_blank\">{$m[1]}</a>";
        }, $line);
        return preg_replace('/\*\*(.+?)\*\*/u', '<strong>$1</strong>', $line);
    }

    /**
     * Texto coletado -> HTML simples: parágrafos nas linhas em branco, <br> nas quebras,
     * <h3> nos títulos do Markdown, <strong> e links. Tudo escapado antes. `markdown`: o
     * texto é Markdown (GitHub), e "#Título" sem espaço também vira título.
     */
    public static function descriptionHtml(?string $text, bool $markdown = false): string
    {
        $heading = $markdown ? '/^#{1,6}\s*(.+)$/u' : '/^#{1,6}\s+(.+)$/u';
        $out = [];
        foreach (preg_split('/\n\s*\n/u', trim(str_replace("\r\n", "\n", $text ?? ''))) as $block) {
            $lines = [];
            foreach (explode("\n", $block) as $raw) {
                $line = Text::e(self::strip($raw));
                if ($line === '') {
                    continue;
                }
                if (preg_match($heading, $line, $m)) {
                    if ($lines) {
                        $out[] = '<p>' . implode("<br>\n", $lines) . '</p>';
                        $lines = [];
                    }
                    $title = preg_replace('/^\*\*(.+)\*\*$/u', '$1', trim(rtrim(trim($m[1]), '#')));
                    $out[] = '<h3>' . self::inline($title) . '</h3>';
                } else {
                    $lines[] = self::inline($line);
                }
            }
            if ($lines) {
                $out[] = '<p>' . implode("<br>\n", $lines) . '</p>';
            }
        }
        return implode("\n", $out);
    }

    /** str.strip() do Python: tira espaços Unicode das pontas. */
    private static function strip(string $s): string
    {
        return preg_replace('/^[\s\x{00A0}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{1C}-\x{1F}\x{85}]+|[\s\x{00A0}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{1C}-\x{1F}\x{85}]+$/u', '', $s);
    }

    /**
     * JSON-LD JobPosting (diretrizes do Google for Jobs) de uma vaga aberta; null sem
     * empresa, sem título ou sem descrição, que o Google exige.
     */
    public static function jobPosting(array $job, string $baseUrl): ?array
    {
        $company = self::employer($job);
        if (!($company && !empty($job['title']) && trim($job['description'] ?? '') !== '')) {
            return null;
        }
        $start = new DateTimeImmutable(self::posted($job));
        $data = [
            '@context' => 'https://schema.org', '@type' => 'JobPosting',
            'title' => trim($job['title']),
            'description' => self::descriptionHtml($job['description']),
            'datePosted' => Dates::utcIso($start),
            'validThrough' => Dates::utcIso($start->modify(sprintf('+%d seconds', (int) round(Dates::maxAgeHours() * 3600)))),
            'hiringOrganization' => ['@type' => 'Organization', 'name' => $company],
            'identifier' => ['@type' => 'PropertyValue', 'name' => self::SOURCE_NAMES[$job['source']] ?? $job['source'],
                'value' => $job['id']],
            'directApply' => false,
            'url' => $baseUrl . Seo::jobPath($job),
        ];
        if ($kind = self::EMPLOYMENT_TYPE[$job['contract'] ?? ''] ?? null) {
            $data['employmentType'] = $kind;
        }
        if (($job['workplace'] ?? null) === 'Remoto') {
            $data['jobLocationType'] = 'TELECOMMUTE';
            $data['applicantLocationRequirements'] = ['@type' => 'Country', 'name' => 'Brasil'];
        } else {
            $data['jobLocation'] = ['@type' => 'Place', 'address' => self::address($job)];
        }
        if ($pay = self::salary($job)) {
            $data['baseSalary'] = $pay;
        }
        return $data;
    }

    /** Vagas abertas de portais parecidas: mesma stack principal e senioridade; completa com a mesma stack. */
    public function similar(array $job): array
    {
        [$name] = self::topic($job);
        $seen = [$job['seq'] => true];
        $out = [];
        foreach ([...(!empty($job['seniority']) ? [$job['seniority']] : []), null] as $seniority) {
            foreach ($this->site->repo->queryJobs(stack: $name, seniority: $seniority, limit: 40) as $r) {
                if ($r['source'] !== 'post' && !isset($seen[$r['seq']]) && count($out) < self::SIMILAR) {
                    $seen[$r['seq']] = true;
                    $out[] = $r;
                }
            }
        }
        return $out;
    }

    // --- HTML ----------------------------------------------------------------------------

    public static function brDatetime(string $iso): string
    {
        return Dates::local(new DateTimeImmutable($iso))->format('d/m/Y \à\s H:i');
    }

    /** "Remoto", "Híbrido · São Paulo, SP", "São Paulo, SP"... */
    public static function place(array $job): ?string
    {
        $loc = trim($job['location'] ?? '');
        if (($job['source'] ?? null) === 'github' && str_contains($loc, '/')) {  // nome do repositório
            $loc = '';
        }
        if (($job['workplace'] ?? null) === 'Remoto' && in_array(self::lower($loc), self::NO_PLACE, true)) {
            $loc = '';
        }
        $out = implode(' · ', array_filter([$job['workplace'] ?? null, $loc]));
        return $out !== '' ? $out : null;
    }

    public static function pageTitle(array $job, bool $isOpen): string
    {
        $title = trim($job['title'] ?: 'Vaga PHP');
        if (!empty($job['company'])) {
            $title .= ' — ' . trim($job['company']);
        }
        if (!empty($job['workplace'])) {
            $title .= " ({$job['workplace']})";
        }
        return $title . ($isOpen ? '' : ' · encerrada') . ' | ' . Seo::SITE_NAME;
    }

    /** Resumo para a meta description: cargo, empresa, modalidade e o começo do texto. */
    public static function summary(array $job, int $limit = 150): string
    {
        $facts = array_values(array_filter(array_map(fn ($k) => $job[$k] ?? null, ['seniority', 'workplace', 'contract'])));
        $head = trim('Vaga ' . ($job['title'] ?: 'PHP'));
        if (!empty($job['company'])) {
            $head .= ' na ' . trim($job['company']);
        }
        $head .= ($facts ? ' (' . implode(', ', $facts) . ')' : '') . '. ';
        $text = $head . trim(preg_replace('/\s+/u', ' ', $job['description'] ?? ''));
        if (mb_strlen($text) <= $limit) {
            return $text;
        }
        $cut = mb_substr($text, 0, $limit - 1);
        $pos = mb_strrpos($cut, ' ');
        $cut = $pos === false ? $cut : mb_substr($cut, 0, $pos);
        return rtrim($cut, ',.;:-') . '…';
    }

    private static function row(string $label, ?string $value): string
    {
        return $value ? '<dt>' . Text::e($label) . '</dt><dd>' . Text::e($value) . '</dd>' : '';
    }

    public static function similarHtml(array $items, string $heading): string
    {
        if (!$items) {
            return '<span id="parecidas"></span>';
        }
        $lis = '';
        foreach ($items as $r) {
            $company = $r['source'] !== 'github' ? ($r['company'] ?? null) : null;  // texto livre lá
            $meta = implode(' · ', array_map(Text::e(...), array_filter([$company, self::place($r), $r['seniority'] ?? null])));
            $lis .= '<li><a href="' . Text::e(Seo::jobPath($r)) . '">' . Text::e($r['title'] ?: 'Vaga PHP') . '</a>'
                . ($meta !== '' ? "<span class=\"meta\">$meta</span>" : '') . '</li>';
        }
        return '<section class="card similar" id="parecidas"><h2>' . Text::e($heading) . "</h2><ul>$lis</ul></section>";
    }

    private static function hoursText(): string
    {
        $h = Dates::maxAgeHours();
        return $h == (int) $h ? (string) (int) $h : (string) $h;
    }

    public static function jobHtml(array $job, bool $isOpen, array $others): string
    {
        $e = Text::e(...);
        [$name, $path] = self::topic($job);
        $source = self::SOURCE_NAMES[$job['source']] ?? $job['source'];
        $out = [];
        if (!$isOpen) {
            $out[] = '<p class="closed" role="status"><strong>Esta vaga não está mais aberta.</strong> '
                . 'Ela foi publicada há mais de ' . self::hoursText() . ' horas ou foi encerrada '
                . 'na fonte. <a href="#parecidas">Veja vagas parecidas abertas</a>.</p>';
            $out[] = self::similarHtml($others, 'Vagas parecidas abertas');
        }
        $out[] = '<article class="card job' . ($isOpen ? '' : ' closed-job') . '">';
        $out[] = '<h1 class="title">' . $e($job['title'] ?: 'Vaga PHP') . '</h1>';
        if (!empty($job['company'])) {
            $out[] = '<p class="company">' . $e($job['company']) . '</p>';
        }
        $posted = self::posted($job);
        $out[] = '<dl class="facts">'
            . self::row('Local', self::place($job)) . self::row('Senioridade', $job['seniority'] ?? null)
            . self::row('Contratação', $job['contract'] ?? null) . self::row('Salário', $job['salary'] ?? null)
            . '<dt>Publicada</dt><dd><time datetime="' . $e($posted) . '">'
            . $e(self::brDatetime($posted)) . '</time> (horário de Brasília)</dd>'
            . self::row('Fonte', $source) . '</dl>';
        if ($stacks = Text::stacks($job['stack'] ?? null)) {
            $out[] = '<div class="chips">' . implode('', array_map(
                fn ($s) => '<a class="chip" href="' . $e(self::topicPath($s)) . '">' . $e($s) . '</a>', $stacks)) . '</div>';
        }
        $here = Seo::jobPath($job);
        if (!empty($job['url']) && $isOpen) {
            $out[] = '<p class="apply"><a class="button" href="' . $e(Site::outHref($job['url'], $job, $here)) . '" '
                . 'rel="nofollow noopener" target="_blank">Candidatar-se no site original '
                . '(' . $e($source) . ')</a>'
                . (isset($job['clicks']) ? ' ' . Site::clicksHtml((int) $job['clicks']) : '') . '</p>';
        }
        if (trim($job['description'] ?? '') !== '') {
            $out[] = '<h2>Descrição</h2><div class="description">'
                . self::descriptionHtml($job['description'], $job['source'] === 'github') . '</div>';
        }
        if (!empty($job['url']) && !$isOpen) {
            $out[] = '<p class="meta">Anúncio original: <a href="' . $e(Site::outHref($job['url'], $job, $here)) . '" '
                . 'rel="nofollow noopener" target="_blank">' . $e($source) . '</a></p>';
        }
        $out[] = '</article>';
        if ($isOpen) {
            $out[] = self::similarHtml($others, 'Vagas parecidas');
        }
        $out[] = '<p class="more"><a href="' . $e($path) . '">Mais vagas ' . $e($name) . '</a>'
            . ' · <a href="/">Todas as vagas abertas</a></p>';
        return implode("\n", $out);
    }

    /** @param list<array{string, string}> $items */
    public static function crumbsHtml(array $items): string
    {
        $links = array_map(fn ($it) => '<a href="' . Text::e($it[1]) . '">' . Text::e($it[0]) . '</a>', array_slice($items, 0, -1));
        return '<nav class="crumbs" aria-label="Caminho">' . implode(' › ', $links)
            . ' › <span aria-current="page">' . Text::e(end($items)[0]) . '</span></nav>';
    }

    private function notFound(Request $request): Response
    {
        $html = Seo::render($request, 'vaga.html', 'Vaga não encontrada | ' . Seo::SITE_NAME,
            'Esta vaga não existe ou foi retirada do site.', $request->path,
            ['vaga' => '<article class="card job"><h1 class="title">Vaga não encontrada</h1>'
                . '<p>Esta vaga não existe ou foi retirada do site.</p>'
                . '<p><a href="/">Ver as vagas abertas</a></p></article>'], noindex: true);
        return Response::html($html, 404);
    }

    public function page(Request $request): Response
    {
        if (!preg_match('/^(\d{1,18})(?:-.*)?$/s', $request->params['ref'], $m)) {
            return $this->notFound($request);
        }
        $repo = $this->site->repo;
        $found = Site::safe(function () use ($repo, $m) {
            $job = $repo->jobBySeq((int) $m[1]);
            if (!$job || $job['source'] === 'post' || !$job['relevant'] || $job['dismissed']) {
                return null;
            }
            // Anunciada de novo (outro id, mesmo título e empresa): vale a mais recente.
            $newest = $repo->newestSeq($job);
            if ($newest && $newest !== (int) $job['seq']) {
                return ['redirect' => Seo::jobPath($repo->jobBySeq($newest))];
            }
            return ['job' => $repo->withClicks([$job])[0], 'open' => self::isOpen($job), 'others' => $this->similar($job)];
        }, null);
        if ($found === null) {
            return $this->notFound($request);
        }
        if (isset($found['redirect'])) {
            return Response::redirect($found['redirect'], 301);
        }
        ['job' => $job, 'open' => $open, 'others' => $others] = $found;
        $path = Seo::jobPath($job);
        if ($request->path !== $path) {
            return Response::redirect($path, 301);
        }
        [$name, $tpath] = self::topic($job);
        $title = trim($job['title'] ?: 'Vaga PHP');
        $trail = [['Início', '/'], ['Vagas', '/vagas']];
        if ($tpath !== '/vagas') {
            $trail[] = [$name, $tpath];
        }
        $trail[] = [$title, $path];
        $jsonld = [Seo::breadcrumbs($request, ...$trail)];
        if ($open && ($posting = self::jobPosting($job, Seo::siteUrl($request)))) {
            array_unshift($jsonld, $posting);
        }
        $html = Seo::render($request, 'vaga.html', self::pageTitle($job, $open), self::summary($job), $path,
            ['crumbs' => self::crumbsHtml($trail), 'vaga' => self::jobHtml($job, $open, $others)], $jsonld, !$open);
        return Response::html($html);
    }
}
