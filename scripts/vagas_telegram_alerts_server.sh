#!/bin/bash
# Telegram: vagas novas agrupadas, rodando no servidor.
set -euo pipefail

ROOT="/home/wouerner/dev/wouerner/vagas-php"
LOG_DIR="$ROOT/data/cron"
LOG_FILE="$LOG_DIR/telegram-alert-server.log"
mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

cd "$ROOT" || exit 1
printf '== vagas (Telegram, servidor) %s ==\n' "$(date '+%Y-%m-%d %H:%M')"

args=(telegram-alert --batch)
if [[ "${VAGAS_TELEGRAM_DRY_RUN:-0}" == "1" ]]; then
  args+=(--dry-run)
fi

docker compose run --rm vagas-php "${args[@]}"
