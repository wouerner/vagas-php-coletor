<?php

declare(strict_types=1);

use VagasPhp\Dates;
use VagasPhp\Site;
use VagasPhp\Vaga;

it('lê faixa e período do salário', function () {
    expect(Vaga::salary(['salary' => 'R$ 4.001 a R$ 5.000']))->toBe(['@type' => 'MonetaryAmount', 'currency' => 'BRL',
        'value' => ['@type' => 'QuantitativeValue', 'unitText' => 'MONTH', 'minValue' => 4001, 'maxValue' => 5000]])
        ->and(Vaga::salary(['salary' => 'US$ 90.000 por ano'])['value']['unitText'])->toBe('YEAR');
});

it('recusa salário incoerente', function (string $salary) {
    expect(Vaga::salary(['salary' => $salary]))->toBeNull();
})->with([
    'dólar sem período' => 'US$ 7.000',
    'abaixo do piso mensal' => 'R$ 100',
    'moedas diferentes' => 'R$ 5.000 a US$ 6.000',
    'sem valor' => 'a combinar',
]);

it('monta o endereço (PostalAddress) a partir do local', function (array $job, array $address) {
    expect(Vaga::address($job))->toBe(['@type' => 'PostalAddress'] + $address + ['addressCountry' => 'BR']);
})->with([
    'cidade e UF' => [['source' => 'gupy', 'location' => 'Campinas, SP, Brasil'],
        ['addressRegion' => 'SP', 'addressLocality' => 'Campinas']],
    'só o estado' => [['source' => 'gupy', 'location' => 'Minas Gerais'], ['addressRegion' => 'Minas Gerais']],
    'capital e região' => [['source' => 'gupy', 'location' => 'São Paulo e Região'], ['addressLocality' => 'São Paulo']],
    'GitHub: só o país' => [['source' => 'github', 'location' => 'São Paulo'], []],
]);

it('escapa a descrição e formata o Markdown', function () {
    $html = Vaga::descriptionHtml("## Requisitos\n**PHP 8** e <script>\n\n[site](https://x.dev) [mail](mailto:a@b.c)", true);
    expect($html)->toBe("<h3>Requisitos</h3>\n<p><strong>PHP 8</strong> e &lt;script&gt;</p>\n"
        . '<p><a href="https://x.dev" rel="nofollow noopener" target="_blank">site</a> mail</p>')
        ->and(Vaga::descriptionHtml('#vagas'))->toBe('<p>#vagas</p>');  // hashtag, não título
});

it('só gera JobPosting com empresa conhecida', function () {
    $job = ['id' => 'gupy:1', 'seq' => 5, 'source' => 'gupy', 'title' => 'Dev PHP', 'description' => 'Texto',
        'company' => 'Acme', 'company_key' => 'acme', 'posted_at' => '2026-10-30T12:00:00+00:00',
        'first_seen' => '2026-10-30T12:00:00+00:00', 'workplace' => 'Remoto', 'contract' => 'PJ'];
    expect(Vaga::jobPosting($job, 'https://example.test'))
        ->validThrough->toBe('2026-11-02T12:00:00+00:00')
        ->employmentType->toBe('CONTRACTOR')
        ->url->toBe('https://example.test/vaga/5-dev-php')
        ->and(Vaga::jobPosting(['company_key' => null] + $job, 'https://example.test'))->toBeNull()
        ->and(Vaga::jobPosting(['source' => 'github'] + $job, 'https://example.test'))->toBeNull();
});

it('corta o resumo numa palavra', function () {
    $job = ['title' => 'Dev PHP', 'company' => 'Acme', 'seniority' => 'Pleno', 'description' => str_repeat('palavra ', 40)];
    expect(Vaga::summary($job, 60))->toBe('Vaga Dev PHP na Acme (Pleno). palavra palavra palavra…');
});

it('mostra a idade da vaga em faixas', function () {
    Dates::$now = new DateTimeImmutable('2026-10-30T15:00:00+00:00', new DateTimeZone('UTC'));
    expect(Site::age('2026-10-30T14:20:00+00:00'))
        ->toBe(['text' => '40 min', 'band' => 'new', 'label' => 'nova', 'at' => '30/10, 11:20'])
        ->and(Site::age('2026-10-29T12:00:00+00:00'))->text->toBe('1 d 3 h')->band->toBe('days')
        ->and(Site::ago('2026-10-27T12:00:00+00:00'))->toBe('há 3 dias');
});
