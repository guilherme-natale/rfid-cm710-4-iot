# 📡 Sistema de Rastreamento RFID - CM710-4

Sistema completo de gerenciamento e monitoramento RFID para Raspberry Pi 4 com módulo Chainway CM710-4.

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RASPBERRY PI 4 (Edge/Local)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐         │
│  │  Script RFID    │───►│  Producer        │───►│  RabbitMQ       │         │
│  │  (rfid_reader)  │    │  (Docker)        │    │  (Docker)       │         │
│  │  - GPIO/Serial  │    │  - Prometheus    │    │  - Management   │         │
│  └─────────────────┘    └──────────────────┘    └────────┬────────┘         │
│                                                           │                   │
│  ┌────────────────────────────────────────────────────────┤                  │
│  │  Prometheus + Grafana + Node Exporter (Monitoramento)  │                  │
│  └────────────────────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────┼──────────────────┘
                                                            │
                                                            │ Internet/VPN
                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLOUD (DigitalOcean/Contabo)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐        │
│  │  RabbitMQ        │───►│  Consumer        │───►│  InfluxDB       │        │
│  │  (Central)       │    │  (Multi-device)  │    │  (Time-series)  │        │
│  └──────────────────┘    └──────────────────┘    └────────┬────────┘        │
│                                   │                        │                  │
│                                   ▼                        │                  │
│                          ┌──────────────────┐              │                  │
│                          │  PostgreSQL      │              │                  │
│                          │  (Metadata)      │              │                  │
│                          └──────────────────┘              │                  │
│                                                            │                  │
│  ┌─────────────────────────────────────────────────────────┤                 │
│  │  API Server + Grafana + Prometheus (Visualização)       │                 │
│  └─────────────────────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Estrutura do Projeto

```
rfid-cm710-4-iot/
├── 📁 local/                    # Deploy LOCAL (Raspberry Pi)
│   ├── docker-compose.yml       # Orquestração local
│   ├── .env.example             # Variáveis de ambiente
│   ├── prometheus/              # Configuração Prometheus
│   └── grafana/                 # Dashboards Grafana
│
├── 📁 cloud/                    # Deploy CLOUD
│   ├── docker-compose.yml       # Orquestração cloud
│   ├── .env.example             # Variáveis de ambiente
│   ├── prometheus/              # Configuração Prometheus
│   ├── grafana/                 # Dashboards Grafana
│   ├── postgres/                # Scripts SQL
│   └── nginx/                   # Reverse proxy (opcional)
│
├── 📁 services/                 # Serviços Docker
│   ├── producer/                # Producer (local)
│   ├── consumer/                # Consumer (cloud)
│   └── api/                     # API REST (cloud)
│
├── 📁 rfid_scripts/             # Scripts RFID para Raspberry Pi
│   ├── rfid_reader.py           # Leitor principal
│   ├── check_config.py          # Verifica configuração
│   └── set_config.py            # Define configuração
│
├── 📁 docs/                     # Documentação
│   ├── LOCAL_INSTALL.md         # Guia instalação local
│   └── CLOUD_INSTALL.md         # Guia instalação cloud
│
├── 📁 .github/workflows/        # CI/CD
│   └── deploy.yml               # Pipeline de deploy
│
└── README.md                    # Este arquivo
```

## 🚀 Quick Start

### Deploy Local (Raspberry Pi)

```bash
# Clonar repositório
git clone https://github.com/guilherme-natale/rfid-cm710-4-iot.git
cd rfid-cm710-4-iot

# Configurar ambiente
cp local/.env.example local/.env
nano local/.env  # Editar variáveis

# Iniciar serviços
cd local
docker-compose up -d
```

📖 **Guia completo:** [docs/LOCAL_INSTALL.md](docs/LOCAL_INSTALL.md)

### Deploy Cloud (DigitalOcean/Contabo)

```bash
# Configurar ambiente
cp cloud/.env.example cloud/.env
nano cloud/.env  # Editar variáveis

# Iniciar serviços
cd cloud
docker-compose up -d
```

📖 **Guia completo:** [docs/CLOUD_INSTALL.md](docs/CLOUD_INSTALL.md)

## 🔧 Tecnologias Utilizadas

| Componente | Tecnologia | Versão |
|------------|------------|--------|
| Message Broker | RabbitMQ | 3.x |
| Time-series DB | InfluxDB | 2.7 |
| Metadata DB | PostgreSQL | 15 |
| Monitoramento | Prometheus | 2.48 |
| Visualização | Grafana | 10.2 |
| Container | Docker | 24.x |
| Orquestração | Docker Compose | 2.x |
| CI/CD | GitHub Actions | - |

## 📊 Monitoramento

### Dashboards Grafana

- **Sistema Local:** Métricas de hardware do Raspberry Pi
- **Sistema Cloud:** Métricas de todos os dispositivos
- **RFID Overview:** Leituras, TAGs únicas, RSSI, antenas

### Métricas Disponíveis

| Métrica | Descrição |
|---------|-----------|
| `rfid_readings_total` | Total de leituras RFID |
| `rfid_rssi_dbm` | Distribuição de RSSI |
| `rfid_devices_online` | Dispositivos online |
| `node_cpu_seconds_total` | Uso de CPU |
| `node_memory_*` | Uso de memória |
| `node_hwmon_temp_celsius` | Temperatura CPU |

## 🔌 APIs Disponíveis

### Cloud API (porta 8000)

```
GET  /api/readings          # Listar leituras com filtros
GET  /api/devices           # Listar dispositivos
GET  /api/statistics        # Estatísticas agregadas
GET  /health                # Health check
```

### Portas

| Serviço | Local | Cloud |
|---------|-------|-------|
| RabbitMQ AMQP | 5672 | 5672 |
| RabbitMQ Management | 15672 | 15672 |
| InfluxDB | - | 8086 |
| PostgreSQL | - | 5432 |
| API | 8001 | 8000 |
| Prometheus | 9090 | 9090 |
| Grafana | 3001 | 3001 |
| Node Exporter | 9100 | 9100 |

## 🔐 Segurança

### Recomendações para Produção

1. **Altere todas as senhas padrão** nos arquivos `.env`
2. **Use HTTPS** com certificados SSL/TLS
3. **Configure firewall** (ufw/iptables)
4. **Use VPN** para comunicação Raspberry Pi ↔ Cloud
5. **Habilite autenticação** em todos os serviços

```bash
# Exemplo firewall (cloud)
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP
sudo ufw allow 443/tcp    # HTTPS
sudo ufw allow 5672/tcp   # RabbitMQ (restringir por IP)
sudo ufw enable
```

## 🔄 CI/CD

O pipeline de CI/CD é executado automaticamente em tags de release:

1. **Lint e Testes:** Valida código Python
2. **Build:** Constrói imagens Docker multi-arquitetura (amd64/arm64)
3. **Push:** Envia para GitHub Container Registry
4. **Release:** Cria release com changelogs

Para criar um release:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -m 'Add nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

---

**Desenvolvido para Raspberry Pi 4 + Chainway CM710-4**
