# 🛠️ Guia de Instalação do NetCable (TrueNAS)

Este guia explica como instalar o NetCable no seu servidor TrueNAS usando Docker. O sistema irá rodar de forma isolada e salvar os dados (banco de dados) localmente no seu servidor.

## 📋 Pré-requisitos
- TrueNAS SCALE (versão com suporte a Apps/Docker).
- Acesso via Shell (SSH ou painel web).
- Um dataset (pasta) no seu pool para armazenar os dados.

## 🛠️ Passo 1: Criar a pasta de dados
No terminal do TrueNAS, crie a pasta onde o banco de dados será salvo (substitua `ssd-apps/vm` pelo caminho do seu pool):
```bash
mkdir -p /mnt/ssd-apps/vm/netcable
chmod 777 /mnt/ssd-apps/vm/netcable

📝 2: O Arquivo YAML

Vá em Apps > Discover Apps > Custom App > Install via YAML.

Cole o conteúdo do arquivo install/trueNAS.yml (que está no repositório).

⚠️ IMPORTANTE: Antes de instalar, edite o YAML e altere:

ADMIN_USER: O nome de usuário que você quer usar.

ADMIN_PASSWORD: A sua senha (evite #, pois o YAML pode cortar).

O caminho do volume (/mnt/SEU_POOL/...) para o local onde você criou a pasta no Passo 1.

Clique em Install.

🌐 Passo 3: Acessar
Frontend: http://IP_DO_TRUENAS:3080

API (Documentação): http://IP_DO_TRUENAS:8000/docs

🔄 Como atualizar
Sempre que houver uma atualização no código, o GitHub Actions constrói uma nova imagem. No TrueNAS, basta ir em Apps e clicar em Update no app netcable.

🖥️ Notas sobre o Monitoramento
Linux/Switches: Funcionam de primeira (ping/TCP).

Windows: Pode precisar liberar o ICMP (ping) no Firewall do Windows.

Switches "Burros": Cadastre como "Sem IP" (visual).

Documento gerado e mantido pela equipe NetCable.