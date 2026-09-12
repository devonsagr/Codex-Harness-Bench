FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm git ripgrep ca-certificates bash \
    && npm install -g @openai/codex@0.154.0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY fixture/ /app/
RUN codex --version && python --version
