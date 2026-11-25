# Imagem pública (ghcr.io, montada no GitHub Actions): nada de segredo aqui. Sem ARG/ENV
# com credencial; senhas e tokens chegam só na execução, pelas variáveis do Coolify.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt

COPY vagas/ vagas/
COPY docker/entrypoint.sh /entrypoint.sh

# Volumes nomeados (Coolify) herdam o dono destas pastas: o usuário pwuser grava nelas.
RUN mkdir -p /app/data /app/.session && chown pwuser:pwuser /app/data /app/.session

# Roda com o UID do host (ver docker-compose.yml); HOME gravável para o Chromium.
# MALLOC_ARENA_MAX=2: as fontes coletam em paralelo, cada uma numa thread, e o glibc criava
# uma arena de 64 MB por thread que nunca voltava ao sistema (coletor com ~1 GB depois de
# um dia; com 2 arenas, ~400 MB com a mesma carga).
ENV HOME=/tmp DISPLAY=:99 PYTHONUNBUFFERED=1 MALLOC_ARENA_MAX=2
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
