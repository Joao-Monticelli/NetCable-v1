services:
  backend:
    container_name: netcable_backend
    environment:
      - PYTHONUNBUFFERED=1
      # =======================================================
      # 👇 ALTERE AQUI: DEFINA SEU USUÁRIO E SENHA DE ACESSO 👇
      # =======================================================
      - ADMIN_USER=seu_usuario_aqui
      - ADMIN_PASSWORD=sua_senha_forte_aqui
    image: ghcr.io/joao-monticelli/netcable-backend:latest
    ports:
      - "8000:8000"
    restart: unless-stopped
    volumes:
      # =======================================================
      # 👇 ALTERE AQUI: CAMINHO DO POOL ONDE OS DADOS SERÃO SALVOS 👇
      # Substitua "/mnt/SEU_POOL/apps/netcable" pelo caminho do seu TrueNAS.
      # Exemplo: /mnt/tank/apps/netcable ou /mnt/ssd-apps/vm/netcable
      # =======================================================
      - /mnt/SEU_POOL/apps/netcable:/app/data

  frontend:
    container_name: netcable_frontend
    depends_on:
      - backend
    image: ghcr.io/joao-monticelli/netcable-frontend:latest
    ports:
      - "8080:80"
    restart: unless-stopped
