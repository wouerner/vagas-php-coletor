<?php

declare(strict_types=1);

namespace VagasPhp;

use PDO;
use PDOException;
use PDOStatement;
use RuntimeException;

/**
 * Conexão com o MySQL do coletor. DATABASE_URL=mysql://usuario:senha@host:3306/base, com
 * ?ssl-mode=REQUIRED|VERIFY_CA|VERIFY_IDENTITY (e ?ssl-ca=/caminho.pem) como no cliente
 * mysql. Senha com caracteres especiais vai codificada (@ -> %40).
 */
final class Db
{
    private ?PDO $pdo = null;

    public function __construct(private readonly ?string $url = null)
    {
    }

    public static function fromEnv(): self
    {
        $url = getenv('DATABASE_URL');
        return new self($url === false ? null : $url);
    }

    /** @return array{string, string, string, array<int, mixed>} dsn, usuário, senha e opções */
    public static function connectArgs(?string $url): array
    {
        if ($url === null || $url === '') {
            throw new RuntimeException('defina DATABASE_URL=mysql://usuario:senha@host:3306/base');
        }
        $u = parse_url($url);
        $db = rawurldecode(trim($u['path'] ?? '', '/'));
        if ($u === false || !in_array($u['scheme'] ?? '', ['mysql', 'mysql+pymysql'], true) || $db === '') {
            throw new RuntimeException('DATABASE_URL deve ser mysql://usuario:senha@host:3306/base');
        }
        parse_str($u['query'] ?? '', $params);
        $params = array_change_key_case($params);
        $mode = strtoupper((string) ($params['ssl-mode'] ?? $params['ssl_mode'] ?? 'DISABLED'));
        $options = [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
            PDO::ATTR_STRINGIFY_FETCHES => false,
            PDO::ATTR_TIMEOUT => 10,
            // sql_mode padrão do MySQL 8 (bancos gerenciados podem vir com ANSI_QUOTES etc.).
            \Pdo\Mysql::ATTR_INIT_COMMAND => "SET SESSION sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,"
                . "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', "
                . "time_zone = '+00:00'",
        ];
        if ($mode === 'REQUIRED') {
            $options[\Pdo\Mysql::ATTR_SSL_CA] = '';
            $options[\Pdo\Mysql::ATTR_SSL_VERIFY_SERVER_CERT] = false;
        } elseif ($mode === 'VERIFY_CA' || $mode === 'VERIFY_IDENTITY') {
            $options[\Pdo\Mysql::ATTR_SSL_CA] = (string) ($params['ssl-ca'] ?? '/etc/ssl/certs/ca-certificates.crt');
            $options[\Pdo\Mysql::ATTR_SSL_VERIFY_SERVER_CERT] = true;
        } elseif ($mode !== 'DISABLED' && $mode !== 'PREFERRED') {
            throw new RuntimeException("ssl-mode inválido: $mode");
        }
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $u['host'] ?? 'localhost', $u['port'] ?? 3306, $db);
        return [$dsn, rawurldecode($u['user'] ?? ''), rawurldecode($u['pass'] ?? ''), $options];
    }

    public function pdo(): PDO
    {
        if ($this->pdo === null) {
            [$dsn, $user, $pass, $options] = self::connectArgs($this->url);
            $this->pdo = new PDO($dsn, $user, $pass, $options);
        }
        return $this->pdo;
    }

    /** @param list<mixed> $args */
    public function query(string $sql, array $args = []): PDOStatement
    {
        $st = $this->pdo()->prepare($sql);
        $st->execute($args);
        return $st;
    }

    /** @return list<array<string, mixed>> */
    public function all(string $sql, array $args = []): array
    {
        return $this->query($sql, $args)->fetchAll();
    }

    /** @return array<string, mixed>|null */
    public function one(string $sql, array $args = []): ?array
    {
        $row = $this->query($sql, $args)->fetch();
        return $row === false ? null : $row;
    }

    public function scalar(string $sql, array $args = []): mixed
    {
        $v = $this->query($sql, $args)->fetchColumn();
        return $v === false ? null : $v;
    }

    /** Tabela ou coluna que ainda não existe: o coletor ainda não criou a base. */
    public static function isMissingTable(PDOException $e): bool
    {
        return in_array($e->getCode(), ['42S02', '42S22'], true);
    }
}
