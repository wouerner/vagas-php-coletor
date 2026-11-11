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

it('usa a paleta azul-petróleo e a marca no tenant go', function () {
    Brand::use('go');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#006b84')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Go</span></h1>')
        ->toContain('<option>Gin</option>')->toContain('Go, Golang e Gin')
        ->not->toContain('<option>Go</option>')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
    expect(Seo::template('index.html'))->toContain('/mercado-go')->not->toContain('/mercado-php');
    expect(Brand::get('lang_lower'))->toBe('go');
    expect(Brand::name())->toBe('Vagas Go');
});

it('usa a paleta verde-oliva e a marca no tenant mobile', function () {
    Brand::use('mobile');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#5a6b00')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Mobile</span></h1>')
        ->toContain('<option>Android</option>')->toContain('<option>React Native</option>')
        ->toContain('Mobile, Android e iOS')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
    expect(Seo::template('index.html'))->toContain('/mercado-mobile')->not->toContain('/mercado-php');
    expect(Brand::get('lang_lower'))->toBe('mobile');
    // É uma plataforma: não há stack com o nome do site, e os temas saem das stacks.
    expect(Brand::get('stacks'))->not->toContain(Brand::lang());
    foreach ([Brand::get('stack_workplace'), Brand::get('stack_seniority')] as $combos) {
        expect(array_diff(array_keys($combos), Brand::get('stacks')))->toBe([]);
    }
    expect(VagasPhp\Text::techSlug('React Native'))->toBe('react-native')
        ->and(VagasPhp\Text::techSlug('iOS'))->toBe('ios')
        ->and(VagasPhp\Text::techSlug('Jetpack Compose'))->toBe('jetpack-compose')
        ->and(VagasPhp\Text::techSlug('Objective-C'))->toBe('objective-c');
});

it('usa a paleta magenta e a marca no tenant frontend', function () {
    Brand::use('frontend');
    foreach (['index.html', 'tema.html', 'dashboard.html', 'empresas.html', 'vaga.html'] as $t) {
        $html = Seo::template($t);
        expect($html)->toContain('#b51f7a')->not->toContain('#5b5fa0')->not->toContain('#a3a7e6')
            ->not->toContain('Vagas PHP');
    }
    expect(Seo::template('index.html'))->toContain('<h1>Vagas <span>Front-end</span></h1>')
        ->toContain('<option>React</option>')->toContain('<option>Vue.js</option>')
        ->toContain('<option>Angular</option>')->toContain('Front-end, React, Vue e Angular')
        ->not->toContain('Laravel')->not->toContain('Symfony')->not->toContain('WordPress');
    // O hífen de "Front-end" e o ponto de "Vue.js" ficam fora dos endereços.
    expect(Seo::template('index.html'))->toContain('/mercado-frontend')->not->toContain('/mercado-php');
    expect(Brand::get('lang_lower'))->toBe('frontend');
    expect(VagasPhp\Text::techSlug('Vue.js'))->toBe('vue-js')
        ->and(VagasPhp\Text::techSlug('Next.js'))->toBe('next-js')
        ->and(VagasPhp\Text::techSlug('React'))->toBe('react');
    // É uma área, não uma linguagem: nenhuma stack tem o nome do site (todas viram tema).
    expect(Brand::get('stacks'))->not->toContain(Brand::lang());
    foreach (['stack_workplace', 'stack_seniority'] as $k) {
        expect(array_keys(Brand::get($k)))->toBe(['React', 'Vue.js', 'Angular']);
        expect(array_diff(array_keys(Brand::get($k)), Brand::get('stacks')))->toBe([]);
    }
});
