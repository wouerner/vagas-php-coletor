<?php

declare(strict_types=1);

use VagasPhp\Brand;
use VagasPhp\Http\Request;
use VagasPhp\Seo;
use VagasPhp\Sites;

const SITES = 'vagasphp.wouerner.dev=php, VagasRuby.wouerner.dev=ruby,vagaslua.wouerner.dev=lua';

function hostRequest(string $host, array $headers = []): Request
{
    return new Request('GET', '/', [], ['host' => $host] + $headers, 'http', $host);
}

afterEach(function () {
    Sites::reset();
    putenv('VAGAS_GA_ID');
    putenv('VAGAS_GA_ID_RUBY');
    putenv('VAGAS_GA_ID_LUA');
});

it('lê a lista de domínios e tenants', function () {
    expect(Sites::map(SITES))->toBe([
        'vagasphp.wouerner.dev' => 'php', 'vagasruby.wouerner.dev' => 'ruby', 'vagaslua.wouerner.dev' => 'lua',
    ]);
    expect(Sites::map(''))->toBe([])->and(Sites::map('sem-tenant.dev=, =php, x.dev=ru by'))->toBe([]);
});

it('escolhe o tenant, a marca e o endereço pelo domínio', function (string $host, string $tenant, string $name, string $url) {
    expect(Sites::select(hostRequest($host), SITES))->toBe($tenant)
        ->and(Brand::tenant())->toBe($tenant)
        ->and(Brand::name())->toBe($name)
        ->and(Seo::siteUrl(hostRequest($host)))->toBe($url);
})->with([
    'php' => ['vagasphp.wouerner.dev', 'php', 'Vagas PHP', 'https://vagasphp.wouerner.dev'],
    'ruby com porta e maiúsculas' => ['VAGASRUBY.wouerner.dev:443', 'ruby', 'Vagas Ruby', 'https://vagasruby.wouerner.dev'],
    'lua' => ['vagaslua.wouerner.dev', 'lua', 'Vagas Lua', 'https://vagaslua.wouerner.dev'],
]);

it('domínio fora da lista recebe o primeiro site, com o endereço dele', function () {
    $req = hostRequest('127.0.0.1:8000', ['x-forwarded-host' => 'evil.example']);
    expect(Sites::select($req, SITES))->toBe('php')
        ->and(Seo::siteUrl($req))->toBe('https://vagasphp.wouerner.dev');
});

it('sem VAGAS_SITES fica no modo de um site', function () {
    expect(Sites::select(hostRequest('vagasruby.wouerner.dev'), ''))->toBeNull()
        ->and(Sites::url())->toBeNull();
});

it('cada site usa a variável com o sufixo dele; a geral só vale no site padrão', function () {
    putenv('VAGAS_GA_ID=G-GERAL1234');
    putenv('VAGAS_GA_ID_RUBY=G-RUBY1234');
    Sites::select(hostRequest('vagasruby.wouerner.dev'), SITES);
    expect(Seo::gaId())->toBe('G-RUBY1234');
    Sites::select(hostRequest('vagaslua.wouerner.dev'), SITES);
    expect(Seo::gaId())->toBe('');
    Sites::select(hostRequest('vagasphp.wouerner.dev'), SITES);
    expect(Seo::gaId())->toBe('G-GERAL1234');
});

it('aceita contêiner do Tag Manager (GTM-) e carrega o gtm.js no lugar do gtag.js', function () {
    putenv('VAGAS_GA_ID_LUA=GTM-ABC1234');
    $req = hostRequest('vagaslua.wouerner.dev');
    Sites::select($req, SITES);
    expect(Seo::gaId())->toBe('GTM-ABC1234');
    $html = Seo::plain($req, 'contato.html');
    expect($html)->toContain('googletagmanager.com/gtm.js?id=GTM-ABC1234')
        ->toContain('"gtm.start"')->toContain('gtag("consent", "default"')
        ->not->toContain('gtag/js')->not->toContain('gtag("config"');

    putenv('VAGAS_GA_ID_LUA=G-LUA12345');
    $html = Seo::plain($req, 'contato.html');
    expect($html)->toContain('googletagmanager.com/gtag/js?id=G-LUA12345')
        ->toContain('gtag("config", "G-LUA12345")')->not->toContain('gtm.js');
});

it('mostra as abas de todos os sites no topo, com a do site atual marcada', function () {
    $req = hostRequest('vagasruby.wouerner.dev');
    Sites::select($req, SITES);
    $html = Seo::plain($req, 'contato.html');
    preg_match('#<nav id="site-tabs".*?</nav>#s', $html, $m);
    expect($m)->not->toBeEmpty();
    $nav = $m[0];
    // Uma aba por site, na ordem de VAGAS_SITES; os nomes das outras linguagens não viram "Ruby".
    expect(substr_count($nav, '<a '))->toBe(3)
        ->and($nav)->toMatch('#href="https://vagasphp\.wouerner\.dev/">.*PHP</a>.*vagasruby.*vagaslua#s')
        ->toContain('<a href="https://vagasruby.wouerner.dev/" aria-current="page">')
        ->toContain('height="16">Lua</a>')
        ->not->toContain('Vagas')
        ->and(substr_count($nav, 'aria-current'))->toBe(1);
    // Logo depois do <body>, em todas as páginas renderizadas.
    expect($html)->toMatch('#<body[^>]*>\s*<nav id="site-tabs"#');
    $page = Seo::render($req, 'regras.html', 'Regras', 'Regras do site', '/regras');
    expect($page)->toContain('<nav id="site-tabs"');
});

it('não mostra as abas com um site só nem no print do dashboard', function () {
    $req = hostRequest('vagasphp.wouerner.dev');
    Sites::select($req, '');
    expect(Seo::plain($req, 'contato.html'))->not->toContain('site-tabs');
    Sites::select($req, 'vagasphp.wouerner.dev=php');
    expect(Seo::plain($req, 'contato.html'))->not->toContain('site-tabs');
    Sites::select($req, SITES);
    $print = new Request('GET', '/dashboard', ['print' => '1'], ['host' => 'vagasphp.wouerner.dev'], 'http', 'vagasphp.wouerner.dev');
    expect(Seo::plain($print, 'dashboard.html'))->not->toContain('site-tabs');
});
