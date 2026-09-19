FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 python3-pip python3-venv git && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.154.0 && codex --version
RUN npm install --prefix /opt/review-tools playwright@1.58.2 pnpm@10.17.1 && /opt/review-tools/node_modules/.bin/playwright install --with-deps chromium
ENV NODE_PATH=/opt/review-tools/node_modules
ENV PATH=/opt/review-tools/node_modules/.bin:$PATH
WORKDIR /app
