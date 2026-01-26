# ☁️ Guia de Instalação CLOUD (DigitalOcean / Contabo)

Este guia detalha o processo completo de instalação do sistema RFID CM710-4 em um servidor cloud.

## 📋 Índice

1. [Pré-requisitos](#-pré-requisitos)
2. [Criação do Servidor](#-criação-do-servidor)
3. [Configuração Inicial](#-configuração-inicial)
4. [Instalação do Docker](#-instalação-do-docker)
5. [Deploy dos Serviços](#-deploy-dos-serviços)
6. [Configuração de Segurança](#-configuração-de-segurança)
7. [Configuração SSL/HTTPS](#-configuração-sslhttps-opcional)
8. [Conectar Raspberry Pis](#-conectar-raspberry-pis)
9. [Monitoramento](#-monitoramento)
10. [Manutenção](#-manutenção)
11. [Troubleshooting](#-troubleshooting)

---

## 📦 Pré-requisitos

### Requisitos Mínimos do Servidor

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| vCPUs | 1 | 2+ |
| RAM | 2 GB | 4 GB+ |
| Armazenamento | 50 GB SSD | 100 GB+ SSD |
| Banda | 1 TB/mês | 2 TB+/mês |
| Sistema | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Planos Sugeridos

#### DigitalOcean
- **Desenvolvimento:** Basic Droplet $12/mês (2GB RAM, 1 vCPU)
- **Produção:** Basic Droplet $24/mês (4GB RAM, 2 vCPU)

#### Contabo
- **Desenvolvimento:** VPS S (4GB RAM, 2 vCPU) ~€5/mês
- **Produção:** VPS M (8GB RAM, 4 vCPU) ~€9/mês

---

## 🖥️ Criação do Servidor

### DigitalOcean

1. Acesse [DigitalOcean](https://www.digitalocean.com)
2. Crie uma conta (ganhe $200 de crédito inicial)
3. Clique em **Create** > **Droplets**
4. Configure:
   - **Image:** Ubuntu 22.04 (LTS) x64
   - **Plan:** Basic > Regular > $12/mo ou superior
   - **Region:** Escolha a mais próxima dos seus Raspberry Pis
   - **Authentication:** SSH Keys (recomendado) ou Password
   - **Hostname:** rfid-cloud-server

### Contabo

1. Acesse [Contabo](https://contabo.com)
2. Selecione **VPS S** ou superior
3. Configure:
   - **Location:** Escolha a região mais próxima
   - **Image:** Ubuntu 22.04
   - **Password:** Defina uma senha forte

---

## ⚙️ Configuração Inicial

### 1. Conectar ao Servidor

```bash
# DigitalOcean (com SSH key)
ssh root@<IP_DO_SERVIDOR>

# Contabo (com senha)
ssh root@<IP_DO_SERVIDOR>
```

### 2. Atualizar Sistema

```bash
apt update && apt upgrade -y
apt install -y curl wget git nano htop
```

### 3. Criar Usuário Não-Root

```bash
# Criar usuário
adduser rfid
usermod -aG sudo rfid

# Configurar SSH para o novo usuário
mkdir -p /home/rfid/.ssh
cp ~/.ssh/authorized_keys /home/rfid/.ssh/
chown -R rfid:rfid /home/rfid/.ssh
chmod 700 /home/rfid/.ssh
chmod 600 /home/rfid/.ssh/authorized_keys

# Testar login (em outro terminal)
ssh rfid@<IP_DO_SERVIDOR>
```

### 4. Configurar Timezone

```bash
timedatectl set-timezone America/Sao_Paulo
# Ou seu timezone local
```

### 5. Configurar Hostname

```bash
hostnamectl set-hostname rfid-cloud
echo "127.0.0.1 rfid-cloud" >> /etc/hosts
```

---

## 🐳 Instalação do Docker

### 1. Instalar Docker

```bash
# Remover versões antigas
apt remove docker docker-engine docker.io containerd runc 2>/dev/null

# Instalar dependências
apt install -y ca-certificates curl gnupg lsb-release

# Adicionar chave GPG oficial
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Adicionar repositório
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Adicionar usuário ao grupo docker
usermod -aG docker rfid
```

### 2. Verificar Instalação

```bash
docker --version
docker compose version
docker run hello-world
```

---

## 🚀 Deploy dos Serviços

### 1. Clonar Repositório

```bash
# Mudar para usuário rfid
su - rfid

# Clonar projeto
cd /home/rfid
git clone https://github.com/guilherme-natale/rfid-cm710-4-iot.git
cd rfid-cm710-4-iot
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar arquivo de exemplo
cp cloud/.env.example cloud/.env

# Editar configurações
nano cloud/.env
```

**⚠️ IMPORTANTE: Altere TODAS as senhas padrão!**

```env
# ---------------------------------------------------------------------------
# SERVIDOR
# ---------------------------------------------------------------------------
SERVER_DOMAIN=<SEU_IP_OU_DOMINIO>

# ---------------------------------------------------------------------------
# RABBITMQ - ALTERE A SENHA!
# ---------------------------------------------------------------------------
RABBITMQ_USER=rfid_user
RABBITMQ_PASSWORD=SuaSenhaForte_RabbitMQ_2024!

# ---------------------------------------------------------------------------
# INFLUXDB - ALTERE AS CREDENCIAIS!
# ---------------------------------------------------------------------------
INFLUXDB_USER=admin
INFLUXDB_PASSWORD=SuaSenhaForte_InfluxDB_2024!
INFLUXDB_ORG=rfid_org
INFLUXDB_BUCKET=rfid_readings
# Gere um token seguro: openssl rand -hex 32
INFLUXDB_TOKEN=<SEU_TOKEN_GERADO>

# ---------------------------------------------------------------------------
# POSTGRESQL - ALTERE A SENHA!
# ---------------------------------------------------------------------------
POSTGRES_USER=rfid_user
POSTGRES_PASSWORD=SuaSenhaForte_Postgres_2024!
POSTGRES_DB=rfid_metadata

# ---------------------------------------------------------------------------
# DISPOSITIVOS RFID
# ---------------------------------------------------------------------------
# MACs dos Raspberry Pis (separados por vírgula)
# Obtenha o MAC do Raspberry Pi com: cat /sys/class/net/eth0/address
DEVICE_MACS=D8:3A:DD:B3:E0:7F

# ---------------------------------------------------------------------------
# GRAFANA - ALTERE A SENHA!
# ---------------------------------------------------------------------------
GRAFANA_USER=admin
GRAFANA_PASSWORD=SuaSenhaForte_Grafana_2024!
GRAFANA_URL=http://<SEU_IP>:3001

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS=*
```

### 3. Gerar Token InfluxDB

```bash
# Gerar token seguro
openssl rand -hex 32

# Copie o resultado e cole no .env
```

### 4. Iniciar Serviços

```bash
cd cloud

# Iniciar em background
docker compose up -d

# Verificar status
docker compose ps

# Ver logs (Ctrl+C para sair)
docker compose logs -f
```

### 5. Verificar Serviços

```bash
# RabbitMQ
curl -s http://localhost:15672 | head -5

# InfluxDB
curl -s http://localhost:8086/health

# API
curl -s http://localhost:8000/health

# Prometheus
curl -s http://localhost:9090/-/healthy

# Grafana
curl -s http://localhost:3001/api/health
```

---

## 🔐 Configuração de Segurança

### 1. Configurar Firewall (UFW)

```bash
# Instalar UFW
apt install -y ufw

# Configurar regras
ufw default deny incoming
ufw default allow outgoing

# SSH (sempre primeiro!)
ufw allow 22/tcp

# HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# RabbitMQ AMQP (restringir a IPs específicos em produção)
ufw allow 5672/tcp

# RabbitMQ Management (opcional - pode remover em produção)
ufw allow 15672/tcp

# Grafana
ufw allow 3001/tcp

# API
ufw allow 8000/tcp

# Prometheus (restringir em produção)
# ufw allow 9090/tcp

# Habilitar firewall
ufw enable

# Verificar status
ufw status verbose
```

### 2. Restringir RabbitMQ a IPs Específicos

```bash
# Permitir apenas IPs dos Raspberry Pis
ufw delete allow 5672/tcp
ufw allow from <IP_RASPBERRY_1> to any port 5672
ufw allow from <IP_RASPBERRY_2> to any port 5672
```

### 3. Configurar Fail2Ban

```bash
# Instalar
apt install -y fail2ban

# Criar configuração
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

# Reiniciar
systemctl restart fail2ban
systemctl enable fail2ban
```

### 4. Desabilitar Login Root SSH

```bash
# Editar configuração SSH
nano /etc/ssh/sshd_config
```

Altere:
```
PermitRootLogin no
PasswordAuthentication no  # Se usar SSH keys
```

```bash
systemctl restart sshd
```

---

## 🔒 Configuração SSL/HTTPS (Opcional)

### Opção 1: Let's Encrypt com Certbot

```bash
# Instalar Certbot
apt install -y certbot

# Obter certificado (substitua pelo seu domínio)
certbot certonly --standalone -d rfid.seudominio.com

# Os certificados ficam em:
# /etc/letsencrypt/live/rfid.seudominio.com/fullchain.pem
# /etc/letsencrypt/live/rfid.seudominio.com/privkey.pem
```

### Opção 2: Usar Nginx Reverse Proxy

```bash
# Criar diretório SSL
mkdir -p cloud/nginx/ssl

# Copiar certificados
cp /etc/letsencrypt/live/rfid.seudominio.com/fullchain.pem cloud/nginx/ssl/
cp /etc/letsencrypt/live/rfid.seudominio.com/privkey.pem cloud/nginx/ssl/

# Iniciar com Nginx
cd cloud
docker compose --profile with-nginx up -d nginx
```

---

## 📡 Conectar Raspberry Pis

### 1. Configurar Raspberry Pi para Conectar na Cloud

No **Raspberry Pi**, edite o arquivo `.env`:

```bash
cd /home/pi/rfid-cm710-4-iot/local
nano .env
```

Configure o RabbitMQ para apontar para a cloud:

```env
# RabbitMQ na Cloud
RABBITMQ_HOST=<IP_DO_SERVIDOR_CLOUD>
RABBITMQ_PORT=5672
RABBITMQ_USER=rfid_user
RABBITMQ_PASSWORD=SuaSenhaForte_RabbitMQ_2024!
```

### 2. Atualizar Docker Compose Local

```bash
# Editar docker-compose.yml local para apontar para cloud
nano docker-compose.yml
```

Na seção `producer`, adicione:

```yaml
producer:
  environment:
    RABBITMQ_HOST: <IP_DO_SERVIDOR_CLOUD>
    # ... resto das configurações
```

### 3. Reiniciar Producer Local

```bash
docker compose restart producer
```

### 4. Verificar Conexão

No **servidor cloud**:

```bash
# Ver filas no RabbitMQ
docker compose exec rabbitmq rabbitmqctl list_queues

# Ver logs do consumer
docker compose logs -f consumer
```

---

## 📊 Monitoramento

### Acessar Interfaces

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| RabbitMQ | http://\<IP\>:15672 | rfid_user / sua_senha |
| Grafana | http://\<IP\>:3001 | admin / sua_senha |
| Prometheus | http://\<IP\>:9090 | - |
| API | http://\<IP\>:8000/docs | - |
| InfluxDB | http://\<IP\>:8086 | admin / sua_senha |

### Dashboards Grafana

1. Acesse Grafana
2. Login com suas credenciais
3. Dashboard "RFID Cloud - Overview" é carregado automaticamente

### Métricas RFID

- **Leituras por minuto:** Taxa de leituras de cada dispositivo
- **RSSI médio:** Qualidade do sinal por antena
- **TAGs únicas:** Contagem de EPCs distintos
- **Dispositivos online:** Status de cada Raspberry Pi

---

## 🔧 Manutenção

### Comandos Úteis

```bash
# Ver todos os logs
docker compose logs -f

# Ver logs específicos
docker compose logs -f consumer
docker compose logs -f influxdb

# Reiniciar serviço
docker compose restart consumer

# Verificar uso de recursos
docker stats

# Verificar espaço em disco
df -h
docker system df
```

### Atualizar Sistema

```bash
cd /home/rfid/rfid-cm710-4-iot

# Baixar atualizações
git pull

# Reconstruir imagens
cd cloud
docker compose build

# Reiniciar serviços
docker compose up -d
```

### Backup de Dados

```bash
# Backup InfluxDB
docker compose exec influxdb influx backup /backup/$(date +%Y%m%d)

# Copiar backup
docker cp rfid_influxdb:/backup ./backups/

# Backup PostgreSQL
docker compose exec postgres pg_dump -U rfid_user rfid_metadata > backup_postgres_$(date +%Y%m%d).sql

# Backup volumes Docker
docker run --rm -v cloud_influxdb_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/influxdb_data_$(date +%Y%m%d).tar.gz /data
docker run --rm -v cloud_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz /data
```

### Limpeza de Dados Antigos

```bash
# Limpar imagens não utilizadas
docker image prune -a

# Limpar volumes não utilizados (CUIDADO!)
docker volume prune

# Limpar tudo
docker system prune -a
```

### Renovar Certificados SSL

```bash
# Renovar Let's Encrypt
certbot renew

# Copiar novos certificados
cp /etc/letsencrypt/live/rfid.seudominio.com/* cloud/nginx/ssl/

# Reiniciar Nginx
docker compose restart nginx
```

---

## 🔍 Troubleshooting

### Consumer não recebe mensagens

```bash
# Verificar filas no RabbitMQ
docker compose exec rabbitmq rabbitmqctl list_queues

# Verificar conexões
docker compose exec rabbitmq rabbitmqctl list_connections

# Verificar se DEVICE_MACS está correto
grep DEVICE_MACS .env

# Verificar logs do consumer
docker compose logs -f consumer
```

### InfluxDB não armazena dados

```bash
# Verificar health
curl http://localhost:8086/health

# Verificar bucket existe
docker compose exec influxdb influx bucket list

# Verificar logs
docker compose logs -f influxdb
```

### Erro de conexão do Raspberry Pi

```bash
# No Raspberry Pi, testar conexão
nc -zv <IP_CLOUD> 5672

# Verificar firewall no cloud
ufw status

# Verificar se RabbitMQ está aceitando conexões
docker compose exec rabbitmq rabbitmq-diagnostics check_running
```

### Alto uso de memória/CPU

```bash
# Ver processos
docker stats

# Ver logs de erro
docker compose logs --tail=100 | grep -i error

# Reiniciar serviços problemáticos
docker compose restart <serviço>
```

### Disk space cheio

```bash
# Verificar uso
df -h
docker system df

# Limpar logs do Docker
truncate -s 0 /var/lib/docker/containers/*/*-json.log

# Limpar dados antigos do InfluxDB
# Configure retention policies no InfluxDB
```

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique os logs: `docker compose logs -f`
2. Verifique métricas no Grafana
3. Consulte documentação oficial dos serviços
4. Abra uma [issue no GitHub](https://github.com/guilherme-natale/rfid-cm710-4-iot/issues)

---

## 🔗 Links Úteis

- [Docker Documentation](https://docs.docker.com)
- [DigitalOcean Tutorials](https://www.digitalocean.com/community/tutorials)
- [InfluxDB Documentation](https://docs.influxdata.com)
- [Grafana Documentation](https://grafana.com/docs)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)

---

**Lembre-se:** A documentação local está em [LOCAL_INSTALL.md](LOCAL_INSTALL.md)
