# 🏠 Guia de Instalação LOCAL (Raspberry Pi)

Este guia detalha o processo completo de instalação do sistema RFID CM710-4 em um Raspberry Pi 4.

## 📋 Índice

1. [Pré-requisitos](#-pré-requisitos)
2. [Preparação do Raspberry Pi](#-preparação-do-raspberry-pi)
3. [Instalação do Docker](#-instalação-do-docker)
4. [Configuração do Módulo RFID](#-configuração-do-módulo-rfid)
5. [Deploy dos Serviços](#-deploy-dos-serviços)
6. [Configuração do MongoDB Atlas](#-configuração-do-mongodb-atlas)
7. [Monitoramento](#-monitoramento)
8. [Manutenção](#-manutenção)
9. [Troubleshooting](#-troubleshooting)

---

## 📦 Pré-requisitos

### Hardware Necessário

| Item | Especificação |
|------|---------------|
| Raspberry Pi | 4 Model B (4GB+ RAM recomendado) |
| Cartão microSD | 32GB+ Classe 10 ou superior |
| Fonte de alimentação | 5V 3A USB-C |
| Módulo RFID | Chainway CM710-4 |
| Cabo USB | Para conexão do módulo |
| Conexão de rede | Ethernet ou WiFi |

### Software Necessário

- Raspberry Pi OS (Bullseye ou superior) - 64-bit recomendado
- Acesso SSH habilitado
- Conexão à Internet

---

## 🍓 Preparação do Raspberry Pi

### 1. Instalar Raspberry Pi OS

1. Baixe o [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Grave a imagem no cartão microSD
3. Configure WiFi e SSH nas configurações avançadas (Ctrl+Shift+X)

### 2. Primeiro Acesso

```bash
# Conectar via SSH
ssh pi@raspberrypi.local
# Ou pelo IP
ssh pi@<IP_DO_RASPBERRY>
```

### 3. Atualizar o Sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt autoremove -y
sudo reboot
```

### 4. Configurar Hostname (Opcional)

```bash
sudo raspi-config
# Selecione: System Options > Hostname
# Digite o novo nome (ex: rfid-reader-01)
```

### 5. Expandir Filesystem (Se necessário)

```bash
sudo raspi-config
# Selecione: Advanced Options > Expand Filesystem
sudo reboot
```

---

## 🐳 Instalação do Docker

### 1. Instalar Docker

```bash
# Script oficial de instalação
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Aplicar mudanças (ou fazer logout/login)
newgrp docker
```

### 2. Instalar Docker Compose

```bash
# Docker Compose v2 (plugin)
sudo apt install docker-compose-plugin -y

# Verificar instalação
docker --version
docker compose version
```

### 3. Configurar Docker para Iniciar no Boot

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

### 4. Testar Instalação

```bash
docker run hello-world
```

---

## 📡 Configuração do Módulo RFID

### 1. Conectar o Módulo CM710-4

1. Conecte o módulo via USB ao Raspberry Pi
2. Aguarde alguns segundos para reconhecimento

### 2. Verificar Conexão

```bash
# Listar portas seriais
ls -l /dev/ttyUSB* /dev/ttyACM*

# Saída esperada:
# crw-rw---- 1 root dialout 188, 0 Jan 26 10:00 /dev/ttyUSB0
```

### 3. Configurar Permissões

```bash
# Adicionar usuário ao grupo dialout
sudo usermod -aG dialout $USER

# Adicionar usuário ao grupo gpio
sudo usermod -aG gpio $USER

# Aplicar mudanças
newgrp dialout
```

### 4. Criar Diretório de Logs

```bash
# Criar diretório para logs do RFID
mkdir -p /home/$USER/cm710-4
chmod 755 /home/$USER/cm710-4
```

### 5. Configurar Script RFID como Serviço

```bash
# Criar arquivo de serviço
sudo nano /etc/systemd/system/rfid-reader.service
```

Conteúdo do arquivo:

```ini
[Unit]
Description=RFID Reader CM710-4
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rfid-cm710-4-iot/rfid_scripts
ExecStart=/usr/bin/python3 /home/pi/rfid-cm710-4-iot/rfid_scripts/rfid_reader.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/cm710-4/service.log
StandardError=append:/home/pi/cm710-4/service-error.log

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar e iniciar serviço
sudo systemctl daemon-reload
sudo systemctl enable rfid-reader
sudo systemctl start rfid-reader

# Verificar status
sudo systemctl status rfid-reader
```

---

## 🚀 Deploy dos Serviços

### 1. Clonar Repositório

```bash
cd /home/$USER
git clone https://github.com/guilherme-natale/rfid-cm710-4-iot.git
cd rfid-cm710-4-iot
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar arquivo de exemplo
cp local/.env.example local/.env

# Editar configurações
nano local/.env
```

**Configurações importantes:**

```env
# IP do Raspberry Pi (obter com: hostname -I)
HOST_IP=192.168.1.100

# RabbitMQ (alterar em produção!)
RABBITMQ_USER=rfid_user
RABBITMQ_PASSWORD=sua_senha_segura_aqui

# MongoDB Atlas (configurar na seção seguinte)
MONGODB_ATLAS_URL=mongodb+srv://...

# Caminho dos logs
LOG_PATH=/home/pi/cm710-4

# Grafana (alterar em produção!)
GRAFANA_USER=admin
GRAFANA_PASSWORD=sua_senha_grafana
```

### 3. Iniciar Serviços Docker

```bash
cd local

# Iniciar todos os serviços
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f
```

### 4. Verificar Serviços

```bash
# RabbitMQ
curl -s http://localhost:15672 | head -5

# Prometheus
curl -s http://localhost:9090/-/healthy

# Grafana
curl -s http://localhost:3001/api/health
```

---

## 🍃 Configuração do MongoDB Atlas

### 1. Criar Conta no MongoDB Atlas

1. Acesse [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Crie uma conta gratuita
3. Crie um novo cluster (M0 Free Tier)

### 2. Configurar Usuário do Banco

1. No painel do Atlas, vá em **Database Access**
2. Clique em **Add New Database User**
3. Configure:
   - Authentication Method: Password
   - Username: `rfid_user`
   - Password: (gere uma senha forte)
   - Database User Privileges: Read and write to any database

### 3. Configurar Network Access

1. Vá em **Network Access**
2. Clique em **Add IP Address**
3. Opções:
   - **Desenvolvimento:** Allow Access from Anywhere (0.0.0.0/0)
   - **Produção:** Adicione apenas o IP do seu Raspberry Pi

### 4. Obter Connection String

1. No cluster, clique em **Connect**
2. Selecione **Connect your application**
3. Copie a connection string:

```
mongodb+srv://rfid_user:<password>@cluster0.xxxxx.mongodb.net/rfid_db?retryWrites=true&w=majority
```

4. Substitua `<password>` pela senha do usuário

### 5. Atualizar .env

```bash
nano local/.env
```

```env
MONGODB_ATLAS_URL=mongodb+srv://rfid_user:sua_senha@cluster0.xxxxx.mongodb.net/rfid_db?retryWrites=true&w=majority
DB_NAME=rfid_db
```

### 6. Reiniciar Serviços

```bash
cd local
docker compose restart backend
```

---

## 📊 Monitoramento

### Acessar Interfaces

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| RabbitMQ | http://\<IP\>:15672 | rfid_user / sua_senha |
| Grafana | http://\<IP\>:3001 | admin / sua_senha |
| Prometheus | http://\<IP\>:9090 | - |

### Dashboards Grafana

1. Acesse Grafana (http://\<IP\>:3001)
2. Login com suas credenciais
3. O dashboard "RFID System - Local Overview" é carregado automaticamente

### Métricas Disponíveis

- **CPU/Memória/Disco:** Uso de recursos do Raspberry Pi
- **Temperatura:** Temperatura da CPU
- **Rede:** Tráfego de entrada/saída
- **RabbitMQ:** Mensagens na fila

---

## 🔧 Manutenção

### Comandos Úteis

```bash
# Ver logs de todos os serviços
docker compose logs -f

# Ver logs de um serviço específico
docker compose logs -f producer

# Reiniciar um serviço
docker compose restart producer

# Parar todos os serviços
docker compose down

# Atualizar imagens e reiniciar
docker compose pull
docker compose up -d

# Limpar recursos não utilizados
docker system prune -a
```

### Atualizar o Sistema

```bash
cd /home/$USER/rfid-cm710-4-iot

# Baixar atualizações
git pull

# Reconstruir e reiniciar
cd local
docker compose build
docker compose up -d
```

### Backup de Dados

Os dados são armazenados em volumes Docker. Para backup:

```bash
# Backup do volume RabbitMQ
docker run --rm -v local_rabbitmq_data:/data -v $(pwd):/backup alpine tar czf /backup/rabbitmq_backup.tar.gz /data

# Backup dos logs RFID
tar czf rfid_logs_backup.tar.gz /home/$USER/cm710-4/
```

---

## 🔍 Troubleshooting

### Módulo RFID não detectado

```bash
# Verificar conexão USB
lsusb

# Verificar porta serial
dmesg | grep tty

# Verificar permissões
ls -la /dev/ttyUSB0
groups $USER
```

### Serviços não iniciam

```bash
# Verificar logs do Docker
docker compose logs --tail=100

# Verificar recursos do sistema
free -h
df -h

# Reiniciar Docker
sudo systemctl restart docker
```

### RabbitMQ não conecta

```bash
# Verificar se está rodando
docker compose ps rabbitmq

# Verificar logs
docker compose logs rabbitmq

# Testar conexão
docker compose exec rabbitmq rabbitmq-diagnostics check_running
```

### Producer não publica mensagens

```bash
# Verificar se arquivo de log existe
ls -la /home/$USER/cm710-4/cm710-4.log

# Verificar se RFID reader está escrevendo
tail -f /home/$USER/cm710-4/cm710-4.log

# Verificar logs do producer
docker compose logs -f producer
```

### Alta temperatura do CPU

```bash
# Verificar temperatura
vcgencmd measure_temp

# Se > 70°C, considere:
# 1. Adicionar dissipador de calor
# 2. Adicionar cooler
# 3. Melhorar ventilação
```

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique os logs do sistema
2. Consulte a [documentação oficial do CM710-4](https://www.chainway.net)
3. Abra uma [issue no GitHub](https://github.com/guilherme-natale/rfid-cm710-4-iot/issues)

---

**Próximo passo:** Configure o ambiente cloud seguindo o [CLOUD_INSTALL.md](CLOUD_INSTALL.md)
