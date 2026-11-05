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
