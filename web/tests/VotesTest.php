<?php

declare(strict_types=1);

use VagasPhp\Dates;
use VagasPhp\Http\Request;
use VagasPhp\Repo;
use VagasPhp\Site;
use VagasPhp\Vaga;

final class VoteRepo extends Repo
{
    /** @var array<string, array<string, mixed>> */
    public array $jobs;
    /** @var array<string, mixed> */
    public array $meta = [];

    /** @param array<string, array<string, mixed>> $jobs */
    public function __construct(array $jobs)
    {
        $this->jobs = $jobs;
    }

    public function meta(string $name): mixed
    {
        return $this->meta[$name] ?? null;
    }

    public function setMeta(string $name, mixed $value): void
    {
        $this->meta[$name] = $value;
    }

    public function withClicks(array $rows): array
    {
        return $rows;
    }

    public function queryJobs(?string $q = null, ?string $source = null, ?string $workplace = null,
                              ?string $seniority = null, ?string $stack = null, ?float $hours = null,
                              bool $includeClosed = false, int $limit = 50, int $offset = 0): array
    {
        return array_slice(array_values($this->jobs), $offset, $limit);
    }

    public function jobBySeq(int $seq): ?array
    {
        foreach ($this->jobs as $job) {
            if ((int) ($job['seq'] ?? 0) === $seq) {
                return $job;
            }
        }
        return null;
    }

    public function newestSeq(array $job): ?int
    {
        return isset($job['seq']) ? (int) $job['seq'] : null;
    }

    public function trustLevels(): array
    {
        return ['companies' => [], 'recruiters' => []];
    }

    public function stats(): array
    {
        return ['sources' => (object) [], 'last_runs' => [], 'open_total' => count($this->jobs)];
    }
}

function voteJob(int $seq): array
{
    return [
        'id' => "job-$seq",
        'seq' => $seq,
        'source' => 'gupy',
        'title' => "Dev PHP $seq",
        'company' => 'Acme',
        'company_key' => 'acme',
        'description' => 'Texto da vaga',
        'posted_at' => '2026-11-18T12:00:00+00:00',
        'first_seen' => '2026-11-18T12:00:00+00:00',
        'workplace' => 'Remoto',
        'contract' => 'PJ',
        'relevant' => 1,
        'dismissed' => null,
        'closed_at' => null,
        'author' => null,
        'author_url' => null,
        'author_headline' => null,
        'stack' => 'PHP,Laravel',
        'location' => 'São Paulo, SP',
        'path' => "/vaga/$seq-dev-php-$seq",
        'url' => "https://example.test/jobs/$seq",
    ];
}

function voteRequest(string $path, array $query = [], array $headers = []): Request
{
    return new Request('POST', $path, $query,
        ['host' => 'vagasphp.wouerner.dev', 'user-agent' => 'Mozilla/5.0'] + $headers,
        'https', 'vagasphp.wouerner.dev');
}

it('renderiza a barra e os botões true/fake', function () {
    $html = Vaga::jobHtml(voteJob(1), true, [], [], [
        'true' => 7,
        'fake' => 3,
        'total' => 10,
        'session_voted' => false,
        'today_votes' => 1,
        'remaining_today' => 9,
    ], null);

    expect($html)->toContain('Termômetro da vaga')
        ->toContain('Verdadeira')
        ->toContain('Fake')
        ->toContain('7 verdadeiras')
        ->toContain('3 fake')
        ->toContain('restam 9 votos hoje');
});

it('seta cookie de sessão na primeira visita', function () {
    $site = new Site(new VoteRepo(['job-1' => voteJob(1)]), __DIR__);
    $response = $site->handle(new Request('GET', '/vaga/1-dev-php', [], ['host' => 'vagasphp.wouerner.dev'], 'https', 'vagasphp.wouerner.dev'));

    expect($response->headers)->toHaveKey('Set-Cookie')
        ->and($response->headers['Set-Cookie'])->toContain('vagas_vote_session=');
});

it('mostra o termômetro na home', function () {
    $repo = new VoteRepo(['job-1' => voteJob(1)]);
    $repo->setMeta('vagas_vote_state', ['votes' => [[
        'job_id' => 'job-1',
        'choice' => 1,
        'session_key' => str_repeat('a', 32),
        'daily_key' => 'feedbeefcafebabe',
        'at' => '2026-11-18T12:00:00+00:00',
    ]]]);
    $site = new Site($repo, __DIR__);
    $response = $site->handle(new Request('GET', '/', [], ['host' => 'vagasphp.wouerner.dev'], 'https', 'vagasphp.wouerner.dev'));

    expect($response->body)->toContain('Esta vaga é real?')
        ->toContain('Verdadeira')
        ->toContain('Fake');
});

it('card sem votos não mostra barra (pareceria 100% fake)', function () {
    $empty = ['true' => 0, 'fake' => 0, 'total' => 0, 'session_voted' => false, 'today_votes' => 0, 'remaining_today' => 10];
    $html = Site::voteHtml(voteJob(1), $empty);
    expect($html)->toContain('sem votos ainda')->not->toContain('vote-mini-fake');

    $voted = Site::voteHtml(voteJob(1), ['true' => 3, 'fake' => 1, 'total' => 4, 'session_voted' => true, 'remaining_today' => 9]);
    expect($voted)->toContain('3 dizem verdadeira · 1 fake')
        ->toContain('width:75%')
        ->toContain('Você já votou nesta vaga.')
        ->toContain(' disabled');
});

it('responde JSON ao voto feito pelo fetch da home', function () {
    Dates::$now = new DateTimeImmutable('2026-11-18T12:00:00+00:00');
    $repo = new VoteRepo(['job-1' => voteJob(1)]);
    $site = new Site($repo, __DIR__);
    $headers = ['accept' => 'application/json', 'cf-connecting-ip' => '200.1.2.3',
        'cookie' => 'vagas_vote_session=' . str_repeat('c', 32)];

    $ok = $site->handle(voteRequest('/api/votes', ['job' => 'job-1', 'vote' => 'true', 'page' => '/'], $headers));
    $data = json_decode($ok->body, true);
    expect($ok->status)->toBe(200)
        ->and($data['status'])->toBe('ok')
        ->and($data['vote']['true'])->toBe(1)
        ->and($data['vote']['session_voted'])->toBeTrue()
        ->and($data['vote'])->not->toHaveKey('status');

    $again = json_decode($site->handle(voteRequest('/api/votes', ['job' => 'job-1', 'vote' => 'fake'], $headers))->body, true);
    expect($again['status'])->toBe('session')->and($again['vote']['fake'])->toBe(0);

    $bad = $site->handle(voteRequest('/api/votes', ['job' => 'job-1', 'vote' => 'talvez'], $headers));
    expect($bad->status)->toBe(400);
});

it('aceita um voto por sessão e limita em 10 por dia', function () {
    Dates::$now = new DateTimeImmutable('2026-11-18T12:00:00+00:00');
    $jobs = [];
    for ($i = 1; $i <= 11; $i++) {
        $jobs["job-$i"] = voteJob($i);
    }
    $repo = new VoteRepo($jobs);
    $site = new Site($repo, __DIR__);
    $headers = ['host' => 'vagasphp.wouerner.dev', 'user-agent' => 'Mozilla/5.0', 'cf-connecting-ip' => '200.1.2.3'];

    $first = $site->handle(voteRequest('/api/votes', ['job' => 'job-1', 'vote' => 'true'],
        $headers + ['cookie' => 'vagas_vote_session=' . str_repeat('a', 32)]));
    expect($first->status)->toBe(303)
        ->and($first->headers['Location'])->toBe('/vaga/1-dev-php-1?vote=ok');

    $duplicate = $site->handle(voteRequest('/api/votes', ['job' => 'job-1', 'vote' => 'fake'],
        $headers + ['cookie' => 'vagas_vote_session=' . str_repeat('a', 32)]));
    expect($duplicate->headers['Location'])->toContain('vote=session');

    for ($i = 2; $i <= 10; $i++) {
        $resp = $site->handle(voteRequest('/api/votes', ['job' => "job-$i", 'vote' => 'true'],
            $headers + ['cookie' => 'vagas_vote_session=' . sprintf('%032x', $i)]));
        expect($resp->status)->toBe(303);
    }

    $limit = $site->handle(voteRequest('/api/votes', ['job' => 'job-11', 'vote' => 'true'],
        $headers + ['cookie' => 'vagas_vote_session=' . str_repeat('b', 32)]));
    expect($limit->headers['Location'])->toContain('vote=limit');
    expect($repo->meta['vagas_vote_state']['votes'])->toHaveCount(10);
});
