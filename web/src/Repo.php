<?php

declare(strict_types=1);

namespace VagasPhp;

/**
 * Consultas do site na base do coletor. O site só lê, menos os cliques (tabela clicks).
 * O que depende do filtro (php.py do coletor) já vem pronto: jobs.company_key,
 * jobs.author_recruiter e a tabela site_meta (ver docs/contrato-base.md).
 */
final class Repo
{
    /** Fontes, na ordem do coletor (store.SOURCES); site_meta "taxonomy" pode trazer outras. */
    public const SOURCES = ['linkedin', 'gupy', 'post', 'github', 'remotar', 'programathor', 'catho',
        'solides', 'inhire', 'coodesh', 'nerdin', 'recrutei', 'upvagas'];

    /** Colunas internas do contrato que a API não expõe. */
    private const HIDDEN = ['company_key', 'author_recruiter'];

    /**
     * A mesma vaga é anunciada várias vezes (ex.: um ID do LinkedIn por cidade): vale só a
     * mais recente de cada título + empresa da mesma fonte. Igual ao DEDUP do coletor.
     */
    public const DEDUP = "seq IN (SELECT max(seq) FROM jobs GROUP BY source,
             lower(COALESCE(title, '')), lower(COALESCE(company, author, '')))";

    /** @var array<string, mixed> */
    private array $meta = [];

    public function __construct(public readonly Db $db)
    {
    }

    /** Item de site_meta (JSON gravado pelo coletor), ou null. */
    public function meta(string $name): mixed
    {
        if (!array_key_exists($name, $this->meta)) {
            try {
                $v = $this->db->scalar('SELECT value FROM site_meta WHERE name = ?', [$name]);
            } catch (\PDOException $e) {
                if (!Db::isMissingTable($e)) {
                    throw $e;
                }
                $v = null;
            }
            $this->meta[$name] = $v === null ? null : json_decode((string) $v, true);
        }
        return $this->meta[$name];
    }

    /** @return list<string> */
    public function sources(): array
    {
        return $this->meta('taxonomy')['sources'] ?? self::SOURCES;
    }

    /** @param array<string, mixed> $row */
    public static function publicJob(array $row): array
    {
        foreach (self::HIDDEN as $col) {
            unset($row[$col]);
        }
        return $row;
    }

    /** sum()/count() voltam como texto (DECIMAL): número ou null. */
    private static function num(mixed $v): int|float|null
    {
        if ($v === null || is_int($v) || is_float($v)) {
            return $v;
        }
        return str_contains((string) $v, '.') && (float) $v != (int) $v ? (float) $v : (int) $v;
    }

    /** @return list<array<string, mixed>> */
    public function queryJobs(?string $q = null, ?string $source = null, ?string $workplace = null,
                              ?string $seniority = null, ?string $stack = null, ?float $hours = null,
                              bool $includeClosed = false, int $limit = 50, int $offset = 0): array
    {
        $sql = 'SELECT * FROM jobs WHERE 1=1 AND relevant = 1 AND dismissed IS NULL';
        $args = [];
        if (!$includeClosed) {
            $sql .= ' AND closed_at IS NULL';
        }
        if ($source) {
            $sql .= ' AND source = ?';
            $args[] = $source;
        }
        foreach (['workplace' => $workplace, 'seniority' => $seniority] as $col => $value) {
            if ($value) {
                $sql .= " AND $col = ?";
                $args[] = $value;
            }
        }
        if ($stack) {
            $sql .= " AND CONCAT(',', stack, ',') LIKE ?";
            $args[] = "%,$stack,%";
        }
        foreach (preg_split('/\s+/u', trim((string) $q), -1, PREG_SPLIT_NO_EMPTY) as $word) {
            $sql .= ' AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR location LIKE ?)';
            array_push($args, "%$word%", "%$word%", "%$word%", "%$word%");
        }
        // Só vagas publicadas nas últimas `hours` horas, nunca mais que o máximo.
        $sql .= ' AND COALESCE(posted_at, first_seen) >= ?';
        $args[] = Dates::cutoff($hours);
        $sql .= ' AND ' . self::DEDUP;
        $sql .= ' ORDER BY COALESCE(posted_at, first_seen) DESC, first_seen DESC, seq DESC LIMIT ? OFFSET ?';
        array_push($args, $limit, $offset);
        return $this->db->all($sql, $args);
    }

    /** Vagas abertas que o site mostra: o mesmo que queryJobs sem filtros e sem limite. */
    public function openCount(): int
    {
        return (int) $this->db->scalar(
            'SELECT count(*) FROM jobs WHERE relevant = 1 AND dismissed IS NULL
               AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND ' . self::DEDUP,
            [Dates::cutoff()],
        );
    }

    /** @return array<string, mixed>|null */
    private function lastRun(string $source): ?array
    {
        return $this->db->one('SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT 1', [$source]);
    }

    public function stats(): array
    {
        $bySource = [];
        foreach ($this->db->all(
            'SELECT source, count(*) total, sum(relevant AND dismissed IS NULL) relevant,
                    sum(relevant AND dismissed IS NULL AND closed_at IS NULL
                        AND COALESCE(posted_at, first_seen) >= ?) open
             FROM jobs GROUP BY source',
            [Dates::cutoff()],
        ) as $r) {
            $bySource[$r['source']] = ['source' => $r['source'], 'total' => (int) $r['total'],
                'relevant' => self::num($r['relevant']), 'open' => self::num($r['open'])];
        }
        $last = [];
        foreach ($this->sources() as $source) {
            $last[$source] = $this->lastRun($source);
        }
        return ['sources' => (object) $bySource, 'last_runs' => $last, 'open_total' => $this->openCount()];
    }

    /**
     * Fonte, empresa, modalidade, senioridade, contratação e stack das vagas aceitas dos
     * últimos `days` dias, sem as repetidas e incluindo as encerradas (páginas por tema).
     */
    public function jobFacets(int $days = 90): array
    {
        return $this->db->all(
            'SELECT source, company, workplace, seniority, contract, stack,
                    COALESCE(posted_at, first_seen) AS posted
             FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND ' . self::DEDUP . '
               AND COALESCE(posted_at, first_seen) >= ?',
            [Dates::daysAgo($days)],
        );
    }

    /**
     * Números do dashboard. Distribuições: vagas abertas (as que o site mostra). Série
     * diária: vagas novas por dia de publicação (dia de Brasília) nos últimos `days` dias,
     * incluindo as encerradas.
     */
    public function dashboard(int $days = 14): array
    {
        $today = Dates::local(Dates::now())->setTime(0, 0);
        $firstDay = $today->modify('-' . ($days - 1) . ' days');
        $rows = $this->db->all(
            'SELECT source, company, workplace, seniority, contract, stack, closed_at,
                    COALESCE(posted_at, first_seen) AS posted
             FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND ' . self::DEDUP . '
               AND COALESCE(posted_at, first_seen) >= ?',
            [Dates::utcIso($firstDay)],
        );
        [$cut72, $cut24, $cut48] = [Dates::cutoff(), Dates::cutoff(24), Dates::cutoff(48)];
        $live = array_values(array_filter($rows, fn ($r) => strcmp($r['posted'], $cut72) >= 0 && !$r['closed_at']));
        $count = fn (string $key) => Text::mostCommon(array_map(fn ($r) => $r[$key] ?: 'Não informado', $live));

        $sources = $this->sources();
        $daily = [];
        for ($i = 0; $i < $days; $i++) {
            $daily[$firstDay->modify("+$i days")->format('Y-m-d')] = [];
        }
        foreach ($rows as $r) {
            $day = Dates::local(new \DateTimeImmutable($r['posted']))->format('Y-m-d');
            if (isset($daily[$day])) {
                $daily[$day][$r['source']] = ($daily[$day][$r['source']] ?? 0) + 1;
            }
        }
        $stacks = [];
        foreach ($live as $r) {
            foreach (Text::stacks($r['stack']) as $s) {
                if ($s !== 'PHP') {
                    $stacks[] = $s;
                }
            }
        }
        $runs = [];
        foreach ($sources as $source) {
            $day = $this->db->one(
                'SELECT count(*) total, sum(ok = 1) ok, sum(ok = 0) failed, sum(new_jobs) new
                 FROM runs WHERE source = ? AND started_at >= ?',
                [$source, $cut24],
            );
            $lastOk = $this->db->scalar(
                'SELECT finished_at FROM runs WHERE source = ? AND ok = 1 ORDER BY id DESC LIMIT 1',
                [$source],
            );
            $runs[$source] = [
                'last' => $this->lastRun($source),
                'last_24h' => array_map(self::num(...), $day),
                'last_ok_at' => $lastOk,
            ];
        }
        $companies = array_filter(array_map(fn ($r) => $r['company'], $live), fn ($c) => (bool) $c);
        return [
            'max_age_hours' => Dates::maxAgeHours(),
            'kpis' => [
                'open' => count($live),
                'new_24h' => count(array_filter($rows, fn ($r) => strcmp($r['posted'], $cut24) >= 0)),
                'prev_24h' => count(array_filter($rows, fn ($r) => strcmp($r['posted'], $cut48) >= 0 && strcmp($r['posted'], $cut24) < 0)),
                'remote' => count(array_filter($live, fn ($r) => $r['workplace'] === 'Remoto')),
                'companies' => count(array_unique($companies)),
            ],
            'by_source' => array_map(fn ($s) => [$s, count(array_filter($live, fn ($r) => $r['source'] === $s))], $sources),
            'daily' => array_map(
                fn ($d) => ['day' => $d] + array_combine($sources, array_map(fn ($s) => $daily[$d][$s] ?? 0, $sources)),
                array_keys($daily),
            ),
            'workplace' => $count('workplace'),
            'seniority' => $count('seniority'),
            'contract' => $count('contract'),
            'stack' => Text::mostCommon($stacks, 8),
            'companies' => Text::mostCommon($companies, 8),
            'runs' => $runs,
            'collecting_since' => $this->db->scalar('SELECT min(first_seen) FROM jobs'),
        ];
    }

    /** Contagem por regra (gravada pelo coletor) e as vagas descartadas à mão (página /regras). */
    public function ruleStats(): array
    {
        $dismissed = $this->db->all(
            'SELECT source, title, url, dismissed FROM jobs WHERE dismissed IS NOT NULL ORDER BY dismissed DESC',
        );
        return ['counts' => (object) ($this->meta('rule_counts') ?? []), 'dismissed' => $dismissed];
    }

    /**
     * Tech recruiters que publicaram vagas PHP aceitas nos últimos `days` dias, com
     * `minJobs` ou mais. Os perfis de `hidden` (pediram para sair) ficam de fora. Vale o
     * headline mais recente de cada perfil; recrutador é quem o coletor marcou em
     * jobs.author_recruiter (php.is_recruiter).
     *
     * @param list<string> $hidden
     */
    public function recruiters(int $days = 90, int $minJobs = 2, array $hidden = []): array
    {
        $profile = fn (string $url) => strtolower(rtrim(explode('?', $url)[0], '/'));
        $hidden = array_flip(array_map($profile, array_filter($hidden)));
        $people = [];
        foreach ($this->db->all(
            'SELECT author, author_url, author_headline, author_recruiter, stack,
                    COALESCE(posted_at, first_seen) AS posted
             FROM jobs WHERE source = \'post\' AND relevant = 1 AND dismissed IS NULL
               AND author_url IS NOT NULL AND ' . self::DEDUP . '
               AND COALESCE(posted_at, first_seen) >= ?
             ORDER BY posted DESC',
            [Dates::daysAgo($days)],
        ) as $r) {
            $key = $profile($r['author_url']);
            if (isset($hidden[$key])) {
                continue;
            }
            $people[$key] ??= ['name' => $r['author'], 'url' => explode('?', $r['author_url'])[0],
                'headline' => $r['author_headline'], 'jobs' => 0, 'last_posted' => $r['posted'],
                'stack' => [], 'recruiter' => (bool) $r['author_recruiter']];
            $p = &$people[$key];
            if (!$p['headline'] && $r['author_headline']) {  // o mais recente que houver
                $p['headline'] = $r['author_headline'];
                $p['recruiter'] = (bool) $r['author_recruiter'];
            }
            $p['jobs']++;
            foreach (Text::stacks($r['stack']) as $s) {
                if ($s !== 'PHP') {
                    $p['stack'][] = $s;
                }
            }
            unset($p);
        }
        $out = [];
        foreach ($people as $p) {
            if ($p['jobs'] >= $minJobs && $p['headline'] && $p['recruiter']) {
                unset($p['recruiter']);
                $p['stack'] = array_column(Text::mostCommon($p['stack'], 4), 0);
                $out[] = $p;
            }
        }
        usort($out, fn ($a, $b) => [$b['jobs'], $b['last_posted']] <=> [$a['jobs'], $a['last_posted']]);
        return $out;
    }

    /**
     * Empresas que mais anunciaram vagas PHP aceitas nos últimos `days` dias, com
     * `minJobs` ou mais, agrupadas por jobs.company_key (NULL: não diz quem contrata).
     */
    public function companies(int $days = 90, int $minJobs = 2): array
    {
        $companies = [];
        foreach ($this->db->all(
            'SELECT source, company, company_key, workplace, stack,
                    COALESCE(posted_at, first_seen) AS posted
             FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND company IS NOT NULL
               AND ' . self::DEDUP . ' AND COALESCE(posted_at, first_seen) >= ?
             ORDER BY posted DESC',
            [Dates::daysAgo($days)],
        ) as $r) {
            if (!($key = $r['company_key'])) {
                continue;
            }
            $companies[$key] ??= ['names' => [], 'jobs' => 0, 'last_posted' => $r['posted'],
                'sources' => [], 'workplace' => [], 'stack' => []];
            $c = &$companies[$key];
            $c['names'][] = trim($r['company']);
            $c['jobs']++;
            $c['sources'][] = $r['source'];
            $c['workplace'][] = $r['workplace'] ?: 'Não informado';
            foreach (Text::stacks($r['stack']) as $s) {
                if ($s !== 'PHP') {
                    $c['stack'][] = $s;
                }
            }
            unset($c);
        }
        $out = [];
        foreach ($companies as $c) {
            if ($c['jobs'] >= $minJobs) {
                $out[] = ['name' => Text::mostCommon($c['names'], 1)[0][0], 'jobs' => $c['jobs'],
                    'last_posted' => $c['last_posted'],
                    'sources' => array_column(Text::mostCommon($c['sources']), 0),
                    'workplace' => Text::mostCommon($c['workplace']),
                    'stack' => array_column(Text::mostCommon($c['stack'], 4), 0)];
            }
        }
        usort($out, fn ($a, $b) => [$b['jobs'], $b['last_posted']] <=> [$a['jobs'], $a['last_posted']]);
        return $out;
    }

    /** Grava um clique para o anúncio original. Falha na base só vira aviso no log. */
    public function logClick(?string $jobId, string $url, ?string $page, ?string $source): void
    {
        $cut = fn (?string $s, int $n) => ($s === null || $s === '') ? null : mb_substr($s, 0, $n);
        try {
            $this->db->query(
                'INSERT INTO clicks (at, job_id, url, page, source) VALUES (?, ?, ?, ?, ?)',
                [Dates::utcIso(Dates::now()), $cut($jobId, 255), $url, $cut($page, 255), $cut($source, 32)],
            );
        } catch (\Throwable $e) {
            error_log("clique não gravado ({$e->getMessage()}): $url");
        }
    }

    /** Cliques dos últimos `days` dias: total, por vaga, por fonte e por dia (UTC). */
    public function clickStats(int $days = 7): array
    {
        $since = Dates::daysAgo($days);
        $rows = fn (string $sql) => array_map(
            fn ($r) => array_values($r),
            $this->db->query($sql, [$since])->fetchAll(\PDO::FETCH_ASSOC),
        );
        return [
            'total' => (int) $this->db->scalar('SELECT count(*) FROM clicks WHERE at >= ?', [$since]),
            'by_job' => $rows('SELECT job_id, url, count(*) n FROM clicks WHERE at >= ? GROUP BY job_id, url ORDER BY n DESC'),
            'by_source' => $rows('SELECT source, count(*) n FROM clicks WHERE at >= ? GROUP BY source ORDER BY n DESC'),
            'by_day' => $rows('SELECT left(at, 10) day, count(*) FROM clicks WHERE at >= ? GROUP BY day ORDER BY day'),
        ];
    }

    /** @return array<string, mixed>|null */
    public function jobBySeq(int $seq): ?array
    {
        return $this->db->one('SELECT * FROM jobs WHERE seq = ?', [$seq]);
    }

    /** seq mais recente da mesma vaga (fonte + título + empresa), como no DEDUP. */
    public function newestSeq(array $job): ?int
    {
        $v = $this->db->scalar(
            "SELECT max(seq) FROM jobs WHERE source = ? AND lower(COALESCE(title, '')) = lower(?)
               AND lower(COALESCE(company, author, '')) = lower(?)",
            [$job['source'], $job['title'] ?? '', $job['company'] ?: ($job['author'] ?: '')],
        );
        return $v === null ? null : (int) $v;
    }

    /** (seq, source, title, posted) das vagas abertas de portais: sitemap. */
    public function openPortalJobs(): array
    {
        return $this->db->all(
            "SELECT seq, source, title, COALESCE(posted_at, first_seen) AS posted FROM jobs
             WHERE source != 'post' AND relevant = 1 AND dismissed IS NULL
               AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND " . self::DEDUP . '
             ORDER BY posted DESC',
            [Dates::cutoff()],
        );
    }
}
