<?php

declare(strict_types=1);

use VagasPhp\Brand;
use VagasPhp\Seo;

afterEach(fn () => Brand::use(null));

it('mantém as cores do PHP no tenant php', function () {
    Brand::use('php');
    $html = Seo::template('index.html');
    expect($html)->toContain('--accent: #5b5fa0')->toContain('<h1>Vagas <span>PHP</span></h1>');
});

it('usa a paleta vermelho-rubi e a marca no tenant ruby', function () {
    Brand::use('ruby');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#b0281f')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Ruby</span></h1>')
        ->toContain('<option>Rails</option>')->toContain('Ruby, Rails e Sinatra')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
});
