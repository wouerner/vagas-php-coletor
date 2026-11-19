<?php

declare(strict_types=1);

namespace VagasPhp;

use VagasPhp\Http\Request;
use VagasPhp\Http\Response;

final class VoteStore
{
    private const KEY = 'vagas_vote_state';
    private const DAILY_CAP = 10;

    private array $state = ['votes' => []];

    public function __construct(private readonly Repo $repo)
    {
        $raw = $this->repo->meta(self::KEY);
        if (is_array($raw) && isset($raw['votes']) && is_array($raw['votes'])) {
            $this->state = $raw;
        }
    }

    public function sessionKey(Request $request): string
    {
        $cookie = trim((string) ($request->cookies['vagas_vote_session'] ?? ''));
        if (preg_match('/^[0-9a-f]{32}$/', $cookie)) {
            return $cookie;
        }
        return substr(hash_hmac('sha256', implode('|', [
            $request->header('cf-connecting-ip') ?? $request->header('x-forwarded-for') ?? $request->ip,
            $request->header('user-agent') ?? '',
            Dates::local(Dates::now())->format('Y-m-d'),
            bin2hex(random_bytes(16)),
        ]), (string) getenv('DATABASE_URL')), 0, 32);
    }

    public function dailyKey(Request $request): string
    {
        $ip = trim(explode(',', $request->header('cf-connecting-ip') ?? $request->header('x-forwarded-for') ?? $request->ip)[0]);
        $ua = (string) ($request->header('user-agent') ?? '');
        $day = Dates::local(Dates::now())->format('Y-m-d');
        return substr(hash_hmac('sha256', "$day|$ip|$ua", (string) getenv('DATABASE_URL')), 0, 16);
    }

    public function summary(string $jobId, string $sessionKey, string $dailyKey): array
    {
        $true = $fake = $today = 0;
        $sessionVoted = false;
        foreach (($this->state['votes'] ?? []) as $vote) {
            if (($vote['daily_key'] ?? null) === $dailyKey) {
                $today++;
            }
            if (($vote['job_id'] ?? null) !== $jobId) {
                continue;
            }
            if (($vote['session_key'] ?? null) === $sessionKey) {
                $sessionVoted = true;
            }
            if (($vote['choice'] ?? 0) > 0) {
                $true++;
            } else {
                $fake++;
            }
        }
        return [
            'true' => $true,
            'fake' => $fake,
            'total' => $true + $fake,
            'session_voted' => $sessionVoted,
            'today_votes' => $today,
            'remaining_today' => max(0, self::DAILY_CAP - $today),
        ];
    }

    public function vote(string $jobId, bool $truth, string $sessionKey, string $dailyKey): array
    {
        $summary = $this->summary($jobId, $sessionKey, $dailyKey);
        if ($summary['session_voted']) {
            return $summary + ['status' => 'session'];
        }
        if ($summary['today_votes'] >= self::DAILY_CAP) {
            return $summary + ['status' => 'limit'];
        }
        $this->state['votes'][] = [
            'job_id' => $jobId,
            'choice' => $truth ? 1 : 0,
            'session_key' => $sessionKey,
            'daily_key' => $dailyKey,
            'at' => Dates::utcIso(Dates::now()),
        ];
        $this->repo->setMeta(self::KEY, $this->state);
        return $this->summary($jobId, $sessionKey, $dailyKey) + ['status' => 'ok'];
    }
}
