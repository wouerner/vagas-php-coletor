<?php

declare(strict_types=1);

use VagasPhp\Seo;

// Endereço da página de vaga: contrato com o coletor, que anuncia essas URLs ao Google
// (collector/vagas/indexing.py). Os dois lados testam contra contracts/job_paths.json.

it('monta o mesmo endereço de vaga que o coletor', function (array $job, ?string $path) {
    expect(Seo::jobPath($job))->toBe($path);
})->with([
    'gupy senior' => [['seq' => 1, 'source' => 'gupy', 'title' => 'Desenvolvedor(a) PHP Sênior'], '/vaga/1-desenvolvedor-a-php-senior'],
    'linkedin laravel' => [['seq' => 42, 'source' => 'linkedin', 'title' => 'Pessoa Desenvolvedora Back-end — Laravel | 100% Remoto'], '/vaga/42-pessoa-desenvolvedora-back-end-laravel-100-remoto'],
    'github php' => [['seq' => 7, 'source' => 'github', 'title' => '[Remoto] Dev PHP Pleno @ Empresa / São Paulo'], '/vaga/7-remoto-dev-php-pleno-empresa-sao-paulo'],
    'catho sem titulo' => [['seq' => 8, 'source' => 'catho', 'title' => null], '/vaga/8-vaga'],
    'catho emoji' => [['seq' => 9, 'source' => 'catho', 'title' => '🚀 Vaga 💜'], '/vaga/9-vaga'],
    'inhire longo' => [['seq' => 10, 'source' => 'inhire', 'title' => 'Engenheiro de Software Especialista em Arquitetura de Sistemas Distribuídos com PHP, Symfony e Kafka'], '/vaga/10-engenheiro-de-software-especialista-em-arquitetura-de-sistemas-distrib'],
    'solides estagio' => [['seq' => 11, 'source' => 'solides', 'title' => 'ESTÁGIO EM DESENVOLVIMENTO — AÇÃO & INOVAÇÃO'], '/vaga/11-estagio-em-desenvolvimento-acao-inovacao'],
    'post sem pagina' => [['seq' => 12, 'source' => 'post', 'title' => 'Vaga PHP'], null],
    'sem seq' => [['seq' => null, 'source' => 'gupy', 'title' => 'Sem seq'], null],
    'remotar fi' => [['seq' => 13, 'source' => 'remotar', 'title' => 'Ｆｕｌｌ ｗｉｄｔｈ ﬁ ligature'], '/vaga/13-full-width-fi-ligature'],
]);
