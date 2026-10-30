<?php

declare(strict_types=1);

use VagasPhp\Seo;

// Endereço da página de vaga: contrato com o coletor, que anuncia essas URLs ao Google
// (collector/vagas_php/indexing.py). Os dois lados testam contra contracts/job_paths.json.

$cases = json_decode((string) file_get_contents(dirname(__DIR__, 2) . '/contracts/job_paths.json'), true);

it('monta o mesmo endereço de vaga que o coletor', function (array $job, ?string $path) {
    expect(Seo::jobPath($job))->toBe($path);
})->with(array_combine(
    array_map(fn ($c) => json_encode($c['job'], JSON_UNESCAPED_UNICODE), $cases),
    array_map(fn ($c) => [$c['job'], $c['path']], $cases),
));
