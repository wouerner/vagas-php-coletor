<?php

declare(strict_types=1);

use VagasPhp\Text;

it('escapa HTML como o html.escape do Python', function () {
    expect(Text::e('<a href="x">D\'Ávila & Cia</a>'))
        ->toBe('&lt;a href=&quot;x&quot;&gt;D&#x27;Ávila &amp; Cia&lt;/a&gt;');
});

it('arredonda a metade para o par', function () {
    expect(Text::round(62.5))->toBe(62)
        ->and(Text::round(63.5))->toBe(64)
        ->and(Text::pct(6, 9))->toBe('67%');
});

it('conta como o Counter.most_common, mantendo a ordem no empate', function () {
    expect(Text::mostCommon(['a', 'b', 'c', 'b']))->toBe([['b', 2], ['a', 1], ['c', 1]])
        ->and(Text::mostCommon(['a', 'b', 'c', 'b'], 1))->toBe([['b', 2]]);
});

it('junta com "e" e tira acentos', function () {
    expect(Text::joinAnd(['a']))->toBe('a')
        ->and(Text::joinAnd(['a', 'b', 'c']))->toBe('a, b e c')
        ->and(Text::fold('São Paulo Híbrido'))->toBe('sao paulo hibrido');
});

it('codifica a query string como o urlencode do Python', function () {
    expect(Text::query(['q' => 'Acme & Co', 'x' => 'é~']))->toBe('q=Acme+%26+Co&x=%C3%A9~');
});

it('só aceita URL http(s)', function () {
    expect(Text::safeUrl('https://x.dev/a'))->toBe('https://x.dev/a')
        ->and(Text::safeUrl('javascript:alert(1)'))->toBeNull()
        ->and(Text::safeUrl(null))->toBeNull();
});
