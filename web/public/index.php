<?php

declare(strict_types=1);

// Front controller: toda requisição passa por aqui (Apache: FallbackResource; servidor
// embutido: php -S 127.0.0.1:8780 -t public public/index.php).

use VagasPhp\Db;
use VagasPhp\Http\Request;
use VagasPhp\Repo;
use VagasPhp\Site;
use VagasPhp\Sites;

require dirname(__DIR__) . '/vendor/autoload.php';

$request = Request::fromGlobals();
// Vários sites no container (VAGAS_SITES): o domínio escolhe o tenant; sem a lista, VAGAS_TENANT.
$tenant = Sites::select($request);
$site = new Site(new Repo(Db::fromEnv(), $tenant), dirname(__DIR__) . '/assets');
$site->handle($request)->send($request->method === 'HEAD');
