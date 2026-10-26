# Estágio 1: Build da aplicação React
FROM node:18-alpine AS build

WORKDIR /app

# Copia os arquivos de dependência
COPY package*.json ./

# Instala as dependências
RUN npm install

# Copia o código fonte
COPY . .

# GARANTE QUE OS BINÁRIOS DO NODE TÊM PERMISSÃO DE EXECUÇÃO (Resolve o erro 126)
RUN chmod -R +x node_modules/.bin/

# Gera os arquivos estáticos de produção (pasta dist)
RUN npm run build

# Estágio 2: Servidor Web (Nginx)
FROM nginx:alpine

# Copia o arquivo de configuração do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia os arquivos gerados pelo Vite para o Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Expõe a porta 80 do Nginx
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]