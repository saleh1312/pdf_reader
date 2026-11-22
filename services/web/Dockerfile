FROM node:22-alpine

WORKDIR /srv

COPY package.json package-lock.json ./
RUN npm ci

COPY .env index.html vite.config.js ./
COPY src ./src

RUN npm run build

EXPOSE 8080

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "8080", "--strictPort"]
