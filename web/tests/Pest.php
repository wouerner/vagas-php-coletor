<?php

declare(strict_types=1);

use VagasPhp\Dates;

// Testes que fixam o relógio (Dates::$now) não vazam para os outros.
pest()->afterEach(function () {
    Dates::$now = null;
});
