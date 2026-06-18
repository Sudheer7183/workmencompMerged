FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer-cached unless package.json changes)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source — hot-reload via volume mount in docker-compose
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
