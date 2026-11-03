<?php

declare(strict_types=1);

use VagasPhp\Bursts;
use VagasPhp\Dates;

/** Vaga publicada `minutes` minutos antes de 03/11/2026 12:00 UTC. */
function burstJob(int $id, int $minutes, array $extra = []): array
{
    $at = (new DateTimeImmutable('2026-11-03T12:00:00+00:00'))->modify("-$minutes minutes");
    return $extra + ['id' => (string) $id, 'title' => 'Desenvolvedor PHP', 'source' => 'linkedin',
        'company' => 'BairesDev', 'company_key' => 'bairesdev', 'location' => 'São Paulo',
        'url' => "https://example.test/$id", 'path' => "/vaga/$id-dev", 'posted_at' => Dates::utcIso($at),
        'first_seen' => Dates::utcIso($at)];
}

/** Ids de cada item da lista agrupada. */
function burstIds(array $jobs): array
{
    return array_map(fn ($item) => array_column($item, 'id'), Bursts::group($jobs));
}

beforeEach(function () {
    Dates::$now = new DateTimeImmutable('2026-11-03T12:30:00+00:00');
});

it('junta a rajada da BairesDev (16 vagas em 3h31) num card só, mesmo intercalada', function () {
    // Intervalos como os de produção: o maior entre publicações seguidas é 1h36.
    $offsets = [0, 5, 12, 20, 31, 40, 48, 55, 63, 70, 76, 83, 90, 95, 115, 211];
    $titles = [...array_fill(0, 6, 'Desenvolvedor PHP'), ...array_fill(0, 3, 'Senior PHP Developer (Symfony & CodeIgniter)'),
        'Full Stack Developer (React/PHP)', 'Full Stack Developer (React/PHP)', 'Backend Engineer (PHP)',
        'PHP Full-Stack Engineer', 'Semi Senior PHP Developer', 'WordPress Solutions Developer', 'Desenvolvedor PHP'];
    $cities = ['Curitiba', 'Guarulhos', 'Goiânia', 'Natal', 'Rio de Janeiro', 'São Paulo', 'Minas Gerais', 'Brasil'];
    $jobs = [];
    foreach ($offsets as $i => $m) {
        $jobs[] = burstJob(100 + $i, $m, ['title' => $titles[$i], 'location' => $cities[$i % 8]]);
    }
    // Outras empresas no meio da lista (ordenada pela data) não quebram o grupo.
    $jobs[] = burstJob(1, 33, ['company' => 'Acme', 'company_key' => 'acme']);
    $jobs[] = burstJob(2, 100, ['company' => 'Outra', 'company_key' => 'outra']);
    usort($jobs, fn ($a, $b) => strcmp($b['posted_at'], $a['posted_at']));

    $items = Bursts::group($jobs);
    expect($items)->toHaveCount(3)
        ->and(array_map('count', $items))->toBe([16, 1, 1])
        ->and(array_column($items[0], 'id'))->toBe(array_map(fn ($i) => (string) (100 + $i), range(0, 15)));

    $html = Bursts::html($jobs);
    expect(substr_count($html, 'class="job burst'))->toBe(1)
        ->and($html)->toContain('BairesDev · 16 vagas')
        ->and($html)->toContain('publicadas em 3 h 31 min')
        ->and($html)->toContain('7× Desenvolvedor PHP · 3× Senior PHP Developer (Symfony &amp; CodeIgniter) · 2× Full Stack Developer (React/PHP) · e mais 4')
        ->and($html)->toContain('Ver as 16 vagas')
        // As 16 vagas continuam acessíveis dentro do grupo, cada uma com sua página.
        ->and(substr_count($html, '<li class="job'))->toBe(16 + 1 + 2)
        ->and($html)->toContain('href="/vaga/115-dev"');
});

it('mantém junto um intervalo de exatamente 12h e separa 12h01', function () {
    expect(burstIds([burstJob(1, 0), burstJob(2, 12 * 60)]))->toBe([['1', '2']])
        ->and(burstIds([burstJob(1, 0), burstJob(2, 12 * 60 + 1)]))->toBe([['1'], ['2']]);
});

it('encadeia pela publicação anterior e abre grupo novo na onda seguinte', function () {
    // 0h, 10h, 20h: cada uma a 10h da anterior, então um grupo só (a janela total passa de 12h).
    expect(burstIds([burstJob(1, 0), burstJob(2, 600), burstJob(3, 1200)]))->toBe([['1', '2', '3']])
        // Duas ondas separadas por 13h viram dois grupos.
        ->and(burstIds([burstJob(1, 0), burstJob(2, 60), burstJob(3, 840), burstJob(4, 900)]))
        ->toBe([['1', '2'], ['3', '4']]);
});

it('agrupa pelo company_key e, sem ele, pelo nome normalizado', function () {
    // Nomes escritos diferente com o mesmo company_key: mesmo grupo.
    expect(burstIds([burstJob(1, 0, ['company' => 'BairesDev LLC']), burstJob(2, 30, ['company' => 'Bairesdev'])]))
        ->toBe([['1', '2']])
        // Mesmo nome, company_key diferente: empresas diferentes.
        ->and(burstIds([burstJob(1, 0, ['company_key' => 'a']), burstJob(2, 30, ['company_key' => 'b'])]))
        ->toBe([['1'], ['2']])
        // Sem company_key: nome sem acento, caixa e espaços extras.
        ->and(burstIds([burstJob(1, 0, ['company' => 'Empresa  Confidêncial', 'company_key' => null]),
            burstJob(2, 30, ['company' => ' empresa confidencial', 'company_key' => ''])]))->toBe([['1', '2']])
        ->and(burstIds([burstJob(1, 0, ['company' => 'Alfa', 'company_key' => null]),
            burstJob(2, 30, ['company' => 'Beta', 'company_key' => null])]))->toBe([['1'], ['2']])
        // Chave e nome não se misturam: "bairesdev" com chave e "BairesDev" sem chave.
        ->and(burstIds([burstJob(1, 0), burstJob(2, 30, ['company_key' => null])]))->toBe([['1'], ['2']]);
});

it('deixa de fora issues do GitHub e vagas sem empresa ou sem data', function () {
    $github = fn ($id, $m) => burstJob($id, $m, ['source' => 'github', 'company_key' => null]);
    expect(burstIds([$github(1, 0), $github(2, 10), $github(3, 20)]))->toBe([['1'], ['2'], ['3']])
        ->and(Bursts::key(burstJob(1, 0, ['source' => 'github'])))->toBeNull()
        ->and(burstIds([burstJob(1, 0, ['company' => '', 'company_key' => null]),
            burstJob(2, 10, ['company' => null, 'company_key' => null])]))->toBe([['1'], ['2']])
        ->and(burstIds([burstJob(1, 0, ['posted_at' => null, 'first_seen' => null]),
            burstJob(2, 10, ['posted_at' => null, 'first_seen' => null])]))->toBe([['1'], ['2']])
        // Sem posted_at vale first_seen, a mesma data que ordena a lista.
        ->and(burstIds([burstJob(1, 0, ['posted_at' => null]), burstJob(2, 10, ['posted_at' => ''])]))
        ->toBe([['1', '2']])
        // Uma vaga do GitHub no meio da rajada não a quebra.
        ->and(burstIds([burstJob(1, 0), $github(9, 5), burstJob(2, 10)]))->toBe([['1', '2'], ['9']]);
});

it('vaga sozinha sai com o card de sempre', function () {
    $html = Bursts::html([burstJob(1, 0), burstJob(2, 30, ['company' => 'Acme', 'company_key' => 'acme'])]);
    expect($html)->not->toContain('burst')
        ->and(substr_count($html, '<li class="job'))->toBe(2);
});

it('dá ao navegador uma chave opaca, nula onde não agrupa', function () {
    $key = Bursts::publicKey(burstJob(1, 0));
    expect($key)->toMatch('/^[0-9a-f]{16}$/')
        ->and($key)->not->toContain('bairesdev')
        ->and(Bursts::publicKey(burstJob(2, 0, ['company' => 'Outro nome'])))->toBe($key)
        ->and(Bursts::publicKey(burstJob(3, 0, ['source' => 'github'])))->toBeNull()
        ->and(Bursts::publicKey(burstJob(4, 0, ['company' => '', 'company_key' => null])))->toBeNull();
});
