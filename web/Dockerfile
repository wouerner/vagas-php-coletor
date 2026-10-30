# Site do Vagas PHP: PHP 8.5 + Apache, porta 8000. Lê o MySQL do coletor (DATABASE_URL).
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock* ./
RUN composer install --no-dev --no-interaction --no-progress --prefer-dist --optimize-autoloader --no-scripts \
    --ignore-platform-req=ext-intl --ignore-platform-req=ext-pdo_mysql

FROM php:8.5-apache
RUN apt-get update \
    && apt-get install -y --no-install-recommends libicu-dev \
    && docker-php-ext-install intl pdo_mysql \
    && rm -rf /var/lib/apt/lists/*
# Porta 8000 (a mesma do site antigo; o Coolify aponta o domínio para ela). Toda
# requisição vai para public/index.php; variáveis de ambiente chegam ao PHP (getenv).
RUN sed -i 's/^Listen 80$/Listen 8000/' /etc/apache2/ports.conf \
    && printf '%s\n' \
        '<VirtualHost *:8000>' \
        '  DocumentRoot /app/public' \
        '  <Directory /app/public>' \
        '    Require all granted' \
        '    FallbackResource /index.php' \
        '  </Directory>' \
        '  ServerSignature Off' \
        '</VirtualHost>' > /etc/apache2/sites-available/000-default.conf \
    && echo 'ServerName localhost' >> /etc/apache2/apache2.conf \
    && echo 'ServerTokens Prod' >> /etc/apache2/conf-available/security.conf \
    && echo 'variables_order = "EGPCS"' > /usr/local/etc/php/conf.d/env.ini \
    && echo 'expose_php = Off' >> /usr/local/etc/php/conf.d/env.ini \
    && mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"
WORKDIR /app
COPY --from=vendor /app/vendor vendor/
COPY src/ src/
COPY public/ public/
COPY templates/ templates/
COPY assets/ assets/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD php -r 'exit(@file_get_contents("http://127.0.0.1:8000/api/stats") === false ? 1 : 0);'
