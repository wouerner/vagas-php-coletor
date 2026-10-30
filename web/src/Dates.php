<?php

declare(strict_types=1);

namespace VagasPhp;

use DateTimeImmutable;
use DateTimeZone;

/**
 * Datas. Na base tudo fica como texto ISO em UTC ("2026-10-11T14:30:00+00:00"), comparado
 * como string; o site mostra no horário de Brasília. Só interessam vagas publicadas há no
 * máximo maxAgeHours() (VAGAS_MAX_AGE_HOURS, padrão 72).
 */
final class Dates
{
    /** Agora fixo, para testes. */
    public static ?DateTimeImmutable $now = null;

    public static function brasilia(): DateTimeZone
    {
        return new DateTimeZone('America/Sao_Paulo');
    }

    public static function maxAgeHours(): float
    {
        $v = getenv('VAGAS_MAX_AGE_HOURS');
        return is_numeric($v) ? (float) $v : 72.0;
    }

    public static function now(): DateTimeImmutable
    {
        return self::$now ?? new DateTimeImmutable('now', new DateTimeZone('UTC'));
    }

    public static function utcIso(DateTimeImmutable $dt): string
    {
        return $dt->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:sP');
    }

    /** Data/hora (UTC) mais antiga aceita: agora menos `hours` (no máximo maxAgeHours()). */
    public static function cutoff(?float $hours = null): string
    {
        $hours = min($hours ?: self::maxAgeHours(), self::maxAgeHours());
        return self::utcIso(self::now()->modify(sprintf('-%d seconds', (int) round($hours * 3600))));
    }

    public static function daysAgo(int $days): string
    {
        return self::utcIso(self::now()->modify("-$days days"));
    }

    public static function parse(?string $iso): ?DateTimeImmutable
    {
        if ($iso === null || $iso === '') {
            return null;
        }
        try {
            return new DateTimeImmutable($iso);
        } catch (\Exception) {
            return null;
        }
    }

    public static function local(DateTimeImmutable $dt): DateTimeImmutable
    {
        return $dt->setTimezone(self::brasilia());
    }

    /** Segundos entre agora e `dt`. */
    public static function secondsSince(DateTimeImmutable $dt): int
    {
        return self::now()->getTimestamp() - $dt->getTimestamp();
    }
}
