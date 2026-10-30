<?php

declare(strict_types=1);

use VagasPhp\Site;
use VagasPhp\Themes;

const TAXONOMY = ['stacks' => ['PHP', 'Laravel', 'Symfony', 'WordPress'],
    'workplaces' => ['Remoto', 'Híbrido', 'Presencial'],
    'seniorities' => ['Estágio', 'Júnior', 'Pleno', 'Sênior']];

it('monta slugs, nomes e apelidos dos temas', function () {
    $t = new Themes(TAXONOMY);
    expect($t->themes['laravel-remoto']['name'])->toBe('Vagas Laravel remotas')
        ->and($t->themes['php-senior-remoto']['name'])->toBe('Vagas PHP sênior remotas')
        ->and($t->themes['php-estagio']['name'])->toBe('Vagas de estágio em PHP')
        ->and($t->aliases['junior'])->toBe('php-junior')
        // Combinação com stack que a taxonomia não tem (Magento) fica de fora.
        ->and($t->themes)->not->toHaveKey('magento-remoto');
});

it('não tem temas sem a taxonomia do coletor', function () {
    expect((new Themes(null))->themes)->toBe([]);
});

it('ordena os relacionados: mais gerais, mais específicos e vizinhos', function () {
    $t = new Themes(TAXONOMY);
    $counts = ['laravel' => 5, 'remoto' => 9, 'laravel-hibrido' => 1, 'symfony' => 2, 'laravel-senior' => 3];
    // Mais gerais: nenhum; mais específicos (por contagem): laravel-senior, laravel-hibrido;
    // vizinhos: symfony.
    expect(array_column($t->related($t->themes['laravel'], $counts), 'slug'))
        ->toBe(['laravel-senior', 'laravel-hibrido', 'symfony']);
});

it('casa vaga e tema por stack, modalidade e senioridade', function () {
    $theme = (new Themes(TAXONOMY))->themes['laravel-remoto'];
    expect(Themes::matches($theme, ['stack' => 'PHP,Laravel', 'workplace' => 'Remoto']))->toBeTrue()
        ->and(Themes::matches($theme, ['stack' => 'PHP,Laravel', 'workplace' => 'Híbrido']))->toBeFalse()
        ->and(Themes::matches($theme, ['stack' => 'PHP,LaravelX', 'workplace' => 'Remoto']))->toBeFalse();
});

it('separa a expressão de uma regra nas alternativas de primeiro nível', function () {
    expect(Site::alternatives('\\b(php|laravel|code\\s?igniter)\\b'))->toBe(['php', 'laravel', 'code\\s?igniter'])
        ->and(Site::alternatives('a|(b|c)'))->toBe(['a', '(b|c)'])
        ->and(Site::alternatives('(a)x(b)'))->toBe(['(a)x(b)']);
});
