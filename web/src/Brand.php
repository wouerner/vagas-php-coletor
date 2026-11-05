<?php

declare(strict_types=1);

namespace VagasPhp;

/**
 * Identidade pública do site por tenant (VAGAS_TENANT, padrão "php"; o mesmo de Repo):
 * nome, linguagem, frameworks citados nos textos, ícone, canais (Telegram/Instagram),
 * caminho da página de mercado e as stacks do filtro da home. O mesmo código serve o
 * Vagas PHP, o Vagas Ruby e o Vagas Lua; só muda o deploy (VAGAS_TENANT) e o domínio.
 *
 * Os templates marcam os textos de marca com {{brand:chave}} (fill() troca); o PHP usa
 * get(). Os valores de "php" são exatamente os textos de antes do multi-tenant.
 */
final class Brand
{
    private const ICON_PHP = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<ellipse cx='50' cy='50' rx='48' ry='26' fill='%23777BB4'/><text x='50' y='60' font-size='30' "
        . "font-family='Arial' font-weight='bold' text-anchor='middle' fill='white'>php</text></svg>";
    // Rubi (losango vermelho); sem marca registrada de terceiros.
    private const ICON_RUBY = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<polygon points='50,94 6,40 24,10 76,10 94,40' fill='%23CC342D'/>"
        . "<polygon points='50,94 30,40 50,10 70,40' fill='%23E0584F'/>"
        . "<polyline points='6,40 94,40' stroke='%23A91401' stroke-width='3' fill='none'/></svg>";

    // Lua: círculo azul-marinho com uma lua menor em órbita (no espírito do logotipo do Lua).
    private const ICON_LUA = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<circle cx='44' cy='56' r='40' fill='%2300007F'/><circle cx='86' cy='14' r='12' fill='%2300007F'/>"
        . "<text x='44' y='66' font-size='28' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>lua</text></svg>";

    /**
     * Cores do Ruby: troca, nos templates, cada cor da paleta do PHP (roxo, com neutros
     * levemente azulados) pela equivalente em vermelho-rubi (neutros levemente quentes).
     * Claro e escuro; os contrastes de texto ficam no mesmo nível dos do PHP. As cores de
     * estado (idade da vaga, ok, aviso) não mudam.
     */
    private const PALETTE_RUBY = [
        // claro
        '#5b5fa0' => '#b0281f', '#ebecf7' => '#fbe9e7', '#f6f6fa' => '#faf6f5', '#f0f0f5' => '#f5efee',
        '#e3e3ec' => '#ece2e0', '#1d1d2b' => '#2b1d1c', '#5d6070' => '#6b5d5b',
        // escuro
        '#a3a7e6' => '#f2928a', '#2a2b45' => '#45211e', '#13131b' => '#1b1313', '#1c1c27' => '#271c1b',
        '#2d2d3c' => '#3c2d2c', '#262634' => '#342625', '#e8e8f0' => '#f0e8e7', '#a0a2b4' => '#b4a2a0',
    ];

    /** Cores do Lua: o mesmo esquema do Ruby, com azul-marinho no lugar do roxo do PHP. */
    private const PALETTE_LUA = [
        // claro
        '#5b5fa0' => '#1f3d99', '#ebecf7' => '#e6ecfa', '#f6f6fa' => '#f5f7fb', '#f0f0f5' => '#eef1f7',
        '#e3e3ec' => '#e0e5ef', '#1d1d2b' => '#1a1f2e', '#5d6070' => '#5a6276',
        // escuro
        '#a3a7e6' => '#8fb0f5', '#2a2b45' => '#1d2b52', '#13131b' => '#11141c', '#1c1c27' => '#191d29',
        '#2d2d3c' => '#2a2f40', '#262634' => '#232838', '#e8e8f0' => '#e6e9f1', '#a0a2b4' => '#9ea6ba',
    ];

    private const GITHUB = 'https://github.com/wouerner/vagas-php-coletor';

    public const BRANDS = [
        'php' => [
            'lang' => 'PHP',
            'lang_lower' => 'php',
            'name' => 'Vagas PHP',
            // "Vagas PHP, Laravel e Symfony", "vagas de PHP, Laravel e Symfony"
            'frameworks' => 'Laravel e Symfony',
            'frameworks_list' => 'Laravel, Symfony, WordPress',
            'frameworks_etc' => 'Laravel, Symfony, WordPress, Magento...',
            'icon' => self::ICON_PHP,
            'telegram' => 'vagas_php',
            'instagram' => 'vagas_php',
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-php',
            // Preview social (assets/og.png, servida em /og.png): a imagem tem a marca do PHP.
            'og_image' => '/og.png',
            'og_alt' => 'Vagas PHP — vagas de PHP, Laravel e Symfony',
            'stack_example' => 'laravel',
            'stacks_keyword' => 'WordPress',
            'stacks' => ['Laravel', 'Symfony', 'CodeIgniter', 'CakePHP', 'Yii', 'Laminas/Zend', 'Hyperf/Swoole',
                'Livewire', 'Filament', 'Magento', 'WordPress', 'Drupal'],
            'stack_workplace' => ['Laravel' => ['Remoto', 'Híbrido', 'Presencial'], 'Symfony' => ['Remoto'],
                'WordPress' => ['Remoto'], 'Magento' => ['Remoto'], 'CodeIgniter' => ['Remoto'], 'Drupal' => ['Remoto']],
            'stack_seniority' => ['Laravel' => ['Júnior', 'Pleno', 'Sênior']],
            // As cores dos templates já são as do PHP.
            'palette' => [],
        ],
        'ruby' => [
            'lang' => 'Ruby',
            'lang_lower' => 'ruby',
            'name' => 'Vagas Ruby',
            'frameworks' => 'Rails e Sinatra',
            'frameworks_list' => 'Rails, Sinatra, Hanami',
            'frameworks_etc' => 'Rails, Sinatra, Hanami, Hotwire...',
            'icon' => self::ICON_RUBY,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-ruby',
            // Sem imagem própria ainda: sem og:image (a /og.png é a do PHP).
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'rails',
            'stacks_keyword' => 'Hanami',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant ruby), sem a linguagem.
            'stacks' => ['Rails', 'Sinatra', 'Hanami', 'Hotwire', 'Sidekiq', 'RSpec'],
            'stack_workplace' => ['Rails' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['Rails' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_RUBY,
        ],
        'lua' => [
            'lang' => 'Lua',
            'lang_lower' => 'lua',
            'name' => 'Vagas Lua',
            'frameworks' => 'OpenResty e Roblox',
            'frameworks_list' => 'OpenResty, Roblox, LÖVE',
            'frameworks_etc' => 'OpenResty, Roblox, LÖVE, Defold...',
            'icon' => self::ICON_LUA,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-lua',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'openresty',
            'stacks_keyword' => 'LuaJIT',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant lua), sem a linguagem.
            'stacks' => ['LuaJIT', 'Luau', 'OpenResty', 'Nginx', 'Roblox', 'LÖVE', 'Defold', 'Neovim'],
            // Pouco volume de vagas: sem páginas de combinação por stack.
            'stack_workplace' => [],
            'stack_seniority' => [],
            'palette' => self::PALETTE_LUA,
        ],
    ];

    private static ?string $tenant = null;

    /** Tenant do site: VAGAS_TENANT (padrão "php"); um tenant sem marca própria usa a do PHP. */
    public static function tenant(): string
    {
        if (self::$tenant === null) {
            $t = strtolower(trim((string) getenv('VAGAS_TENANT') ?: 'php'));
            self::$tenant = isset(self::BRANDS[$t]) ? $t : 'php';
        }
        return self::$tenant;
    }

    /** Troca o tenant (testes); null volta a ler VAGAS_TENANT. */
    public static function use(?string $tenant): void
    {
        self::$tenant = $tenant === null ? null : (isset(self::BRANDS[$tenant]) ? $tenant : 'php');
    }

    public static function isPhp(): bool
    {
        return self::tenant() === 'php';
    }

    public static function get(string $key): mixed
    {
        return self::BRANDS[self::tenant()][$key];
    }

    /** "PHP" / "Ruby". */
    public static function lang(): string
    {
        return self::get('lang');
    }

    /** "Vagas PHP" / "Vagas Ruby". */
    public static function name(): string
    {
        return self::get('name');
    }

    /** Link do Instagram para os rodapés (" · Instagram"), vazio sem conta. */
    public static function instagramLink(): string
    {
        $ig = self::get('instagram');
        return $ig === null ? '' : ' · <a href="https://www.instagram.com/' . $ig
            . '/" target="_blank" rel="noopener">Instagram</a>';
    }

    /** Convite do Telegram na home, vazio sem canal. */
    public static function telegramInvite(): string
    {
        $tg = self::get('telegram');
        if ($tg === null) {
            return '';
        }
        return '<p class="tg"><span class="tg-long">Receba as vagas de ' . self::lang() . ' no Telegram</span>'
            . '<span class="tg-short">Vagas no Telegram</span>: <a href="https://t.me/' . $tg . '" rel="noopener">'
            . 't.me/' . $tg . '</a></p>';
    }

    /** Bloco do Instagram na página de contato, vazio sem conta. */
    public static function instagramContact(): string
    {
        $ig = self::get('instagram');
        if ($ig === null) {
            return '';
        }
        return "<section class=\"card\" aria-labelledby=\"t-ig\">\n"
            . "    <strong id=\"t-ig\">Instagram</strong>\n"
            . "    <p>Siga o projeto por lá:</p>\n"
            . "    <p class=\"instagram\"><a href=\"https://www.instagram.com/$ig/\" target=\"_blank\" "
            . "rel=\"noopener\">@$ig</a></p>\n"
            . "  </section>\n\n  ";
    }

    /** <option> das stacks do filtro da home. */
    public static function stackOptions(): string
    {
        return implode('', array_map(fn ($s) => '<option>' . Text::e($s) . '</option>', self::get('stacks')));
    }

    /**
     * Troca as marcas {{brand:chave}} do template pelos valores do tenant. Chaves:
     * lang, lang_lower, name, frameworks, frameworks_list, frameworks_etc, icon, github,
     * mercado_path, stack_example, telegram_invite, instagram_link, instagram_contact,
     * stack_options e stacks_json (webmcp.js). O trecho entre {{brand:php_only}} e
     * {{brand:/php_only}} só fica no PHP (fatos que só valem para ele, como fontes de PHP).
     */
    public static function fill(string $html): string
    {
        $b = self::BRANDS[self::tenant()];
        if (str_contains($html, '{{brand:')) {
            $html = (string) preg_replace('#\{\{brand:php_only\}\}(.*?)\{\{brand:/php_only\}\}#s',
                self::isPhp() ? '$1' : '', $html);
            $map = [
                'lang' => $b['lang'], 'lang_lower' => $b['lang_lower'], 'name' => $b['name'],
                'frameworks' => $b['frameworks'], 'frameworks_list' => $b['frameworks_list'],
                'frameworks_etc' => $b['frameworks_etc'], 'icon' => $b['icon'], 'github' => $b['github'],
                'mercado_path' => $b['mercado_path'], 'stack_example' => $b['stack_example'],
                'telegram_invite' => self::telegramInvite(), 'instagram_link' => self::instagramLink(),
                'instagram_contact' => self::instagramContact(), 'stack_options' => self::stackOptions(),
                'stacks_json' => json_encode($b['stacks'], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
            ];
            $html = (string) preg_replace_callback('/\{\{brand:([a-z_]+)\}\}/',
                fn ($m) => $map[$m[1]] ?? $m[0], $html);
        }
        $html = preg_replace('#<link rel="icon" href="[^"]+">#', '<link rel="icon" href="' . self::get('icon') . '">', $html);
        $html = preg_replace('#<p class="tg">.*?</p>#s', self::telegramInvite(), $html);
        $html = preg_replace('#<section class="card" aria-labelledby="t-ig">.*?</section>#s', self::instagramContact(), $html);
        $html = str_replace(' · <a href="https://www.instagram.com/vagas_php/" target="_blank" rel="noopener">Instagram</a>', self::instagramLink(), $html);
        $html = str_replace('/mercado-php', self::get('mercado_path'), $html);
        if (!self::isPhp()) {
            // Textos fixos do PHP nos templates: lista do filtro de stack e frameworks citados.
            $html = (string) preg_replace_callback(
                '#(<select name="stack" aria-label="Stack">\s*<option value="">Stack</option>).*?(\s*</select>)#s',
                fn ($m) => $m[1] . self::stackOptions() . $m[2], $html);
            $html = strtr($html, [
                'Laravel, Symfony, WordPress e outras' => $b['frameworks_list'] . ' e outras',
                'Laravel e Symfony' => $b['frameworks'],
            ]);
        }
        $html = strtr($html, $b['palette']);
        $html = str_replace('Vagas PHP', self::name(), $html);
        $html = preg_replace('/\bPHP\b/', self::lang(), $html);
        return $html === null ? '' : $html;
    }
}
