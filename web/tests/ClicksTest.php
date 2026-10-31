<?php

declare(strict_types=1);

use VagasPhp\Db;
use VagasPhp\Http\Request;
use VagasPhp\Repo;
use VagasPhp\Site;

$job = ['id' => 'gupy:1', 'source' => 'gupy', 'title' => 'Dev PHP', 'url' => 'https://x.gupy.io/jobs/1',
    'posted_at' => null, 'first_seen' => '2026-10-30T12:00:00+00:00'];

it('mostra os cliques no anúncio original com a explicação', function (int $clicks, string $label) use ($job) {
    $html = Site::jobCard($job + ['clicks' => $clicks]);
    expect($html)->toContain("<span class=\"clicks\" tabindex=\"0\">$label<span class=\"tip\" role=\"tooltip\">")
        ->toContain(Site::CLICKS_TIP);
})->with([
    'nenhum' => [0, 'nenhum clique ainda'],
    'um' => [1, '1 clique'],
    'vários' => [12, '12 cliques'],
]);

it('não mostra cliques sem anúncio original ou sem a contagem', function () use ($job) {
    expect(Site::jobCard(['url' => null, 'clicks' => 3] + $job))->not->toContain('class="clicks"')
        ->and(Site::jobCard($job))->not->toContain('class="clicks"');
});

it('não conta clique de robô', function (?string $userAgent, bool $bot) {
    expect(Site::isBot($userAgent))->toBe($bot);
})->with([
    'Chrome' => ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36', false],
    'Safari no iPhone' => ['Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1', false],
    'app do LinkedIn' => ['Mozilla/5.0 (Linux; Android 14; SM-A546E Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/141.0.0.0 Mobile Safari/537.36 [LinkedInApp]/9.31.2', false],
    'Googlebot' => ['Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)', true],
    'Bingbot' => ['Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36', true],
    'LinkedIn' => ['LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)', true],
    'WhatsApp' => ['WhatsApp/2.23.20.0', true],
    'Facebook' => ['facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)', true],
    'Chrome headless' => ['Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/141.0.0.0 Safari/537.36', true],
    'curl' => ['curl/8.5.0', true],
    'Python' => ['python-requests/2.32.3', true],
    'sem user agent' => [null, true],
    'vazio' => ['', true],
]);

it('tira o /out do alcance dos crawlers', function () {
    $site = new Site(new Repo(new Db()), __DIR__);
    expect($site->robots(new Request('GET', '/robots.txt'))->body)->toContain("Disallow: /out\n");
});
