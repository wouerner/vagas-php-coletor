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

it('usa a paleta azul-marinho e a marca no tenant lua', function () {
    Brand::use('lua');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#1f3d99')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Lua</span></h1>')
        ->toContain('<option>OpenResty</option>')->toContain('Lua, OpenResty e Roblox')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
});

it('usa a paleta marrom-alaranjada e a marca no tenant java', function () {
    Brand::use('java');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#a34f12')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Java</span></h1>')
        ->toContain('<option>Spring Boot</option>')->toContain('Java, Spring Boot e Quarkus')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
});

it('usa a paleta azul e amarela e a marca no tenant python', function () {
    Brand::use('python');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#2b6a9e')->toContain('#ffd43b')->not->toContain('#5b5fa0')
            ->not->toContain('#a3a7e6')->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Python</span></h1>')
        ->toContain('<option>Django</option>')->toContain('Python, Django e FastAPI')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
});

it('usa a paleta verde e a marca no tenant nodejs', function () {
    Brand::use('nodejs');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#29722d')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Node.js</span></h1>')
        ->toContain('<option>NestJS</option>')->toContain('Node.js, Express e NestJS')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
    // O ponto de "Node.js" fica fora dos endereços: /mercado-nodejs e /vagas/nodejs-senior.
    expect(Seo::template('index.html'))->toContain('/mercado-nodejs')->not->toContain('/mercado-php');
    expect(Brand::get('lang_lower'))->toBe('nodejs');
});

it('usa a paleta violeta e a marca no tenant dotnet', function () {
    Brand::use('dotnet');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#512bd4')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>.NET</span></h1>')
        ->toContain('<option>C#</option>')->toContain('.NET, C# e ASP.NET')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
    // O ponto de ".NET" e o "#" de "C#" ficam fora dos endereços.
    expect(Seo::template('index.html'))->toContain('/mercado-dotnet')->not->toContain('/mercado-php');
    expect(Brand::get('lang_lower'))->toBe('dotnet');
    expect(VagasPhp\Text::techSlug('C#'))->toBe('c-sharp')
        ->and(VagasPhp\Text::techSlug('F#'))->toBe('f-sharp')
        ->and(VagasPhp\Text::techSlug('ASP.NET'))->toBe('asp-net')
        ->and(VagasPhp\Text::techSlug('Ruby on Rails'))->toBe('ruby-on-rails');
});
