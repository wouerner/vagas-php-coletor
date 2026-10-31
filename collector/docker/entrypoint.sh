#!/usr/bin/env bash
# Comandos (o site fica em web/, em PHP, com imagem própria):
#   serve        -> serviço contínuo (coleta agendada + MCP, se VAGAS_MCP_ENABLED)
#   outros args  -> CLI (python -m vagas ...), ex.: collect all
# Para serve/CLI sobe display virtual + VNC + noVNC, para acompanhar o navegador e
# concluir verificações do LinkedIn (2FA/captcha).
set -euo pipefail

# O container pode ser reaproveitado entre execuções: limpa a trava do display.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
for _ in $(seq 1 50); do [ -e /tmp/.X11-unix/X99 ] && break; sleep 0.1; done
if [ ! -e /tmp/.X11-unix/X99 ]; then
  echo "Xvfb não iniciou:" >&2; cat /tmp/xvfb.log >&2; exit 1
fi
x11vnc -display :99 -rfbport 5900 -forever -shared -nopw -quiet >/dev/null 2>&1 &
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &
sleep 1
echo "Navegador visível no noVNC (porta NOVNC_PUBLISH_PORT do host, padrão 6081)."

if [ "${1:-}" = "serve" ]; then
  exec python -m vagas.service
fi
exec python -m vagas "$@"
