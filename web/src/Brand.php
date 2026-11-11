<?php

declare(strict_types=1);

namespace VagasPhp;

/**
 * Identidade pública do site por tenant (VAGAS_TENANT, padrão "php"; o mesmo de Repo):
 * nome, linguagem, frameworks citados nos textos, ícone, canais (Telegram/Instagram),
 * caminho da página de mercado e as stacks do filtro da home. O mesmo código serve o
 * Vagas PHP, o Vagas Ruby, o Vagas Lua, o Vagas Java, o Vagas Python, o Vagas Node.js, o Vagas .NET, o Vagas Go, o Vagas Front-end e o Vagas Mobile; só muda o deploy (VAGAS_TENANT)
 * e o domínio.
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

    // Java: quadrado laranja-café com chaves e o nome; sem a xícara (marca registrada).
    private const ICON_JAVA = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<rect x='4' y='16' width='92' height='68' rx='16' fill='%23A34F12'/>"
        . "<text x='50' y='61' font-size='28' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>java</text></svg>";

    // Python: dois quadrados sobrepostos, azul e amarelo (as cores da linguagem), com "py";
    // sem as cobras do logotipo (marca registrada).
    private const ICON_PYTHON = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<rect x='28' y='28' width='68' height='68' rx='16' fill='%23FFD43B'/>"
        . "<rect x='4' y='4' width='68' height='68' rx='16' fill='%233776AB'/>"
        . "<text x='38' y='49' font-size='34' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>py</text></svg>";

    // Node.js: hexágono verde com o nome (forma genérica; não é o logotipo, marca registrada).
    private const ICON_NODEJS = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<polygon points='50,3 91,26 91,74 50,97 9,74 9,26' fill='%2329722D'/>"
        . "<text x='50' y='59' font-size='26' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>node</text></svg>";

    // .NET: quadrado violeta com o nome (forma genérica; não é o logotipo, marca registrada).
    private const ICON_DOTNET = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<rect width='100' height='100' rx='18' fill='%23512BD4'/>"
        . "<text x='50' y='61' font-size='30' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>.NET</text></svg>";

    // Go: círculo azul-petróleo com o nome (forma genérica; não é o logotipo nem o gopher,
    // marcas registradas).
    private const ICON_GO = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<circle cx='50' cy='50' r='48' fill='%23006B84'/>"
        . "<text x='50' y='66' font-size='46' font-family='Arial' font-weight='bold' text-anchor='middle' "
        . "fill='white'>Go</text></svg>";

    // Mobile: silhueta de smartphone verde-oliva, com a tela e a barra de gestos (forma genérica;
    // sem o robô do Android nem a maçã, marcas registradas).
    private const ICON_MOBILE = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<rect x='24' y='3' width='52' height='94' rx='12' fill='%235A6B00'/>"
        . "<rect x='31' y='14' width='38' height='64' rx='4' fill='white'/>"
        . "<rect x='40' y='85' width='20' height='5' rx='2.5' fill='white'/></svg>";

    // Front-end: quadrado magenta com os sinais de marcação "</>" (forma genérica; nenhum
    // logotipo de framework).
    private const ICON_FRONTEND = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        . "<rect width='100' height='100' rx='18' fill='%23B51F7A'/>"
        . "<path d='M36 30 16 50l20 20M64 30l20 20-20 20M56 24 44 76' fill='none' stroke='white' "
        . "stroke-width='8' stroke-linecap='round' stroke-linejoin='round'/></svg>";

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

    /** Cores do Java: o mesmo esquema do Ruby, com laranja-café no lugar do roxo do PHP. */
    private const PALETTE_JAVA = [
        // claro
        '#5b5fa0' => '#a34f12', '#ebecf7' => '#fbeee3', '#f6f6fa' => '#faf7f4', '#f0f0f5' => '#f5f0eb',
        '#e3e3ec' => '#ede4dc', '#1d1d2b' => '#2b211a', '#5d6070' => '#6b6058',
        // escuro
        '#a3a7e6' => '#f0a868', '#2a2b45' => '#45301e', '#13131b' => '#1b1613', '#1c1c27' => '#271f1a',
        '#2d2d3c' => '#3c322b', '#262634' => '#342b25', '#e8e8f0' => '#f0ebe7', '#a0a2b4' => '#b4a89f',
    ];

    /**
     * Cores do Python: o mesmo esquema do Ruby, com o azul do Python no lugar do roxo do PHP
     * no tema claro e o amarelo no escuro (o amarelo não tem contraste sobre fundo claro).
     */
    private const PALETTE_PYTHON = [
        // claro
        '#5b5fa0' => '#2b6a9e', '#ebecf7' => '#e4eff8', '#f6f6fa' => '#f5f8fa', '#f0f0f5' => '#eef2f5',
        '#e3e3ec' => '#dfe6ec', '#1d1d2b' => '#1a232b', '#5d6070' => '#586570',
        // escuro
        '#a3a7e6' => '#ffd43b', '#2a2b45' => '#3d3514', '#13131b' => '#12161a', '#1c1c27' => '#1a2026',
        '#2d2d3c' => '#2b333b', '#262634' => '#242b32', '#e8e8f0' => '#e7ecf0', '#a0a2b4' => '#9faab4',
    ];

    /**
     * Cores do Node.js: o mesmo esquema do Ruby, com verde no lugar do roxo do PHP. O verde
     * da marca (#339933) é claro demais para texto em fundo branco: no tema claro entra um
     * tom mais escuro dele, e no escuro, um mais claro.
     */
    private const PALETTE_NODEJS = [
        // claro
        '#5b5fa0' => '#29722d', '#ebecf7' => '#e6f4e6', '#f6f6fa' => '#f5f8f5', '#f0f0f5' => '#eef3ee',
        '#e3e3ec' => '#dfe7df', '#1d1d2b' => '#1b251c', '#5d6070' => '#586459',
        // escuro
        '#a3a7e6' => '#8ccf8a', '#2a2b45' => '#1f3d22', '#13131b' => '#121712', '#1c1c27' => '#1a211a',
        '#2d2d3c' => '#2c362c', '#262634' => '#252e25', '#e8e8f0' => '#e7eee7', '#a0a2b4' => '#a0aea1',
    ];

    /**
     * Cores do .NET: o mesmo esquema do Ruby, com o violeta da marca (#512BD4) no lugar do
     * roxo acinzentado do PHP; no tema escuro entra um tom mais claro dele.
     */
    private const PALETTE_DOTNET = [
        // claro
        '#5b5fa0' => '#512bd4', '#ebecf7' => '#ece8fb', '#f6f6fa' => '#f7f6fc', '#f0f0f5' => '#f1eff8',
        '#e3e3ec' => '#e4e1f0', '#1d1d2b' => '#1c1830', '#5d6070' => '#5e5a75',
        // escuro
        '#a3a7e6' => '#b9a8ff', '#2a2b45' => '#2e2460', '#13131b' => '#13111c', '#1c1c27' => '#1b1929',
        '#2d2d3c' => '#2f2b40', '#262634' => '#272337', '#e8e8f0' => '#eae8f3', '#a0a2b4' => '#a5a1b9',
    ];

    /**
     * Cores do Go: o mesmo esquema do Ruby, com azul-petróleo no lugar do roxo do PHP. O
     * ciano da marca (#00ADD8) é claro demais para texto em fundo branco: no tema claro
     * entra um tom mais escuro dele, e no escuro, um mais claro.
     */
    private const PALETTE_GO = [
        // claro
        '#5b5fa0' => '#006b84', '#ebecf7' => '#e2f4f8', '#f6f6fa' => '#f4f8f9', '#f0f0f5' => '#edf3f5',
        '#e3e3ec' => '#dde7ea', '#1d1d2b' => '#16242a', '#5d6070' => '#55656b',
        // escuro
        '#a3a7e6' => '#5fd0ea', '#2a2b45' => '#0f3a47', '#13131b' => '#101619', '#1c1c27' => '#182024',
        '#2d2d3c' => '#29353a', '#262634' => '#222d31', '#e8e8f0' => '#e6eef0', '#a0a2b4' => '#9eafb5',
    ];

    /**
     * Cores do Mobile: o mesmo esquema do Ruby, com verde-oliva no lugar do roxo do PHP (não é
     * cor de nenhuma das plataformas: o site cobre Android e iOS); no tema escuro entra um
     * verde-limão claro.
     */
    private const PALETTE_MOBILE = [
        // claro
        '#5b5fa0' => '#5a6b00', '#ebecf7' => '#f1f5dc', '#f6f6fa' => '#f8f9f3', '#f0f0f5' => '#f2f4ea',
        '#e3e3ec' => '#e5e8d8', '#1d1d2b' => '#22261a', '#5d6070' => '#62685a',
        // escuro
        '#a3a7e6' => '#c5d86d', '#2a2b45' => '#353d14', '#13131b' => '#15170f', '#1c1c27' => '#1f2218',
        '#2d2d3c' => '#33372a', '#262634' => '#2b2f22', '#e8e8f0' => '#ecefe4', '#a0a2b4' => '#a9ae9c',
    ];

    /**
     * Cores do Front-end: o mesmo esquema do Ruby, com magenta no lugar do roxo do PHP (a
     * faixa de cor que ainda não tinha site, entre o violeta do .NET e o vermelho do Ruby);
     * no tema escuro entra um rosa mais claro.
     */
    private const PALETTE_FRONTEND = [
        // claro
        '#5b5fa0' => '#b51f7a', '#ebecf7' => '#fbe7f3', '#f6f6fa' => '#faf6f9', '#f0f0f5' => '#f5eef2',
        '#e3e3ec' => '#ede0e8', '#1d1d2b' => '#2b1a25', '#5d6070' => '#6b5864',
        // escuro
        '#a3a7e6' => '#ff8fd0', '#2a2b45' => '#4a1d3a', '#13131b' => '#1b1318', '#1c1c27' => '#271b23',
        '#2d2d3c' => '#3c2c36', '#262634' => '#34252e', '#e8e8f0' => '#f0e7ec', '#a0a2b4' => '#b4a0ac',
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
        'java' => [
            'lang' => 'Java',
            'lang_lower' => 'java',
            'name' => 'Vagas Java',
            'frameworks' => 'Spring Boot e Quarkus',
            'frameworks_list' => 'Spring Boot, Quarkus, Micronaut',
            'frameworks_etc' => 'Spring Boot, Quarkus, Micronaut, Jakarta EE...',
            'icon' => self::ICON_JAVA,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-java',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'spring-boot',
            'stacks_keyword' => 'Quarkus',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant java), sem a linguagem.
            'stacks' => ['Spring Boot', 'Spring', 'Quarkus', 'Micronaut', 'Jakarta EE', 'Hibernate'],
            'stack_workplace' => ['Spring Boot' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['Spring Boot' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_JAVA,
        ],
        'python' => [
            'lang' => 'Python',
            'lang_lower' => 'python',
            'name' => 'Vagas Python',
            'frameworks' => 'Django e FastAPI',
            'frameworks_list' => 'Django, Flask, FastAPI',
            'frameworks_etc' => 'Django, Flask, FastAPI, Celery...',
            'icon' => self::ICON_PYTHON,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-python',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'django',
            'stacks_keyword' => 'FastAPI',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant python), sem a linguagem.
            'stacks' => ['Django', 'Flask', 'FastAPI', 'Celery', 'SQLAlchemy', 'Pytest'],
            'stack_workplace' => ['Django' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['Django' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_PYTHON,
        ],
        'nodejs' => [
            'lang' => 'Node.js',
            // Sem o ponto: entra em endereços (/vagas/nodejs-senior).
            'lang_lower' => 'nodejs',
            'name' => 'Vagas Node.js',
            'frameworks' => 'Express e NestJS',
            'frameworks_list' => 'Express, NestJS, Fastify',
            'frameworks_etc' => 'Express, NestJS, Fastify, AdonisJS...',
            'icon' => self::ICON_NODEJS,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-nodejs',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'nestjs',
            'stacks_keyword' => 'Fastify',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant nodejs), sem a linguagem.
            'stacks' => ['Express', 'NestJS', 'Fastify', 'AdonisJS', 'Koa', 'TypeScript'],
            'stack_workplace' => ['NestJS' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['NestJS' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_NODEJS,
        ],
        'dotnet' => [
            'lang' => '.NET',
            // Sem o ponto: entra em endereços (/vagas/dotnet-senior).
            'lang_lower' => 'dotnet',
            'name' => 'Vagas .NET',
            'frameworks' => 'C# e ASP.NET',
            'frameworks_list' => 'C#, ASP.NET, Blazor',
            'frameworks_etc' => 'C#, ASP.NET, Blazor, Entity Framework...',
            'icon' => self::ICON_DOTNET,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-dotnet',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'c-sharp',
            'stacks_keyword' => 'Blazor',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant dotnet), sem a linguagem.
            'stacks' => ['C#', 'ASP.NET', 'Blazor', 'Entity Framework', 'MAUI', 'Xamarin', 'WPF', 'F#', 'VB.NET'],
            'stack_workplace' => ['C#' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['C#' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_DOTNET,
        ],
        'go' => [
            'lang' => 'Go',
            'lang_lower' => 'go',
            'name' => 'Vagas Go',
            'frameworks' => 'Golang e Gin',
            'frameworks_list' => 'Golang, Gin, Echo',
            'frameworks_etc' => 'Golang, Gin, Echo, Fiber, gRPC...',
            'icon' => self::ICON_GO,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-go',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'gin',
            'stacks_keyword' => 'gRPC',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant go), sem a linguagem.
            'stacks' => ['Gin', 'Echo', 'Fiber', 'GORM', 'gRPC', 'Kubernetes'],
            'stack_workplace' => ['Gin' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['Gin' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_GO,
        ],
        'mobile' => [
            // Plataforma, não linguagem: um site só para Android, iOS e multiplataforma.
            'lang' => 'Mobile',
            'lang_lower' => 'mobile',
            'name' => 'Vagas Mobile',
            'frameworks' => 'Android e iOS',
            'frameworks_list' => 'Android, iOS, Flutter',
            'frameworks_etc' => 'Android, iOS, Flutter, React Native...',
            'icon' => self::ICON_MOBILE,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-mobile',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'android',
            'stacks_keyword' => 'React Native',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant mobile); não há
            // stack com o nome do site ("Mobile").
            'stacks' => ['Android', 'iOS', 'Kotlin', 'Swift', 'Flutter', 'React Native', 'SwiftUI', 'Jetpack Compose',
                'Kotlin Multiplatform', 'Dart', 'Objective-C', 'Ionic', 'Xamarin', 'MAUI'],
            'stack_workplace' => ['Android' => ['Remoto', 'Híbrido', 'Presencial'], 'iOS' => ['Remoto', 'Híbrido', 'Presencial'],
                'Flutter' => ['Remoto', 'Híbrido', 'Presencial']],
            'stack_seniority' => ['Android' => ['Júnior', 'Pleno', 'Sênior'], 'iOS' => ['Júnior', 'Pleno', 'Sênior'],
                'Flutter' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_MOBILE,
        ],
        'frontend' => [
            // Uma área, não uma linguagem: nenhuma stack tem este nome (todas viram tema).
            'lang' => 'Front-end',
            // Sem o hífen: entra em endereços (/vagas/frontend-senior).
            'lang_lower' => 'frontend',
            'name' => 'Vagas Front-end',
            'frameworks' => 'React, Vue e Angular',
            'frameworks_list' => 'React, Vue.js, Angular',
            'frameworks_etc' => 'React, Vue.js, Angular, Next.js...',
            'icon' => self::ICON_FRONTEND,
            'telegram' => null,
            'instagram' => null,
            'github' => self::GITHUB,
            'mercado_path' => '/mercado-frontend',
            'og_image' => null,
            'og_alt' => null,
            'stack_example' => 'react',
            'stacks_keyword' => 'Angular',
            // As stacks do coletor (collector/vagas/config_defaults.json, tenant frontend).
            'stacks' => ['React', 'Vue.js', 'Angular', 'Next.js', 'Nuxt', 'Svelte', 'TypeScript', 'JavaScript',
                'Tailwind', 'Redux'],
            'stack_workplace' => ['React' => ['Remoto', 'Híbrido', 'Presencial'], 'Vue.js' => ['Remoto'],
                'Angular' => ['Remoto']],
            'stack_seniority' => ['React' => ['Júnior', 'Pleno', 'Sênior'], 'Vue.js' => ['Júnior', 'Pleno', 'Sênior'],
                'Angular' => ['Júnior', 'Pleno', 'Sênior']],
            'palette' => self::PALETTE_FRONTEND,
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
