FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    chromium \
    librsvg2-bin \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-freefont-ttf \
    fonts-cmu \
  && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install --production

COPY fonts/ /app/fonts/
COPY server.js ./

EXPOSE 8081

CMD ["node", "server.js"]
