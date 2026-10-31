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
ENV HOME=/tmp DISPLAY=:99 PYTHONUNBUFFERED=1
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
