# Estágio 1: Build da aplicação React
FROM node:20-alpine AS build

WORKDIR /app

# Instala as dependências exatamente como no package-lock.json
COPY package*.json ./
RUN npm ci

# Copia o código fonte e gera o build de produção
COPY . .
RUN npm run build

# Estágio 2: Servidor Web (Nginx)
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
