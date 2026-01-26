# RFID CM710-4 IoT - PRD

## Problema Original
Transformar repositório RFID em Docker completo com:
- Deploy local (Raspberry Pi)
- Deploy cloud (DigitalOcean/Contabo)
- Remover MongoDB local (usar MongoDB Atlas)
- Documentação separada (LOCAL e CLOUD)
- Docker Compose para orquestração
- CI/CD pipeline (GitHub Actions)
- Monitoramento (Prometheus/Grafana)

## Arquitetura Implementada
```
Raspberry Pi (Local)        ────────────>        Cloud Server
├── RFID Script                                  ├── RabbitMQ Central
├── Producer (Docker)                            ├── Consumer (Docker)
├── RabbitMQ (Docker)                            ├── InfluxDB (Time-series)
├── Backend API (Docker)                         ├── PostgreSQL (Metadata)
├── Prometheus                                   ├── API Server
├── Grafana                                      ├── Prometheus
└── Node Exporter                                ├── Grafana
                                                 ├── cAdvisor
                                                 └── Nginx (opcional)
```

## O Que Foi Implementado ✅

### Docker Compose
- [x] `local/docker-compose.yml` - Deploy completo para Raspberry Pi
- [x] `cloud/docker-compose.yml` - Deploy completo para cloud

### CI/CD
- [x] `.github/workflows/deploy.yml` - Pipeline automático em tags de release
- [x] Build multi-arquitetura (amd64/arm64)
- [x] Push para GitHub Container Registry

### Monitoramento
- [x] Prometheus configurado (local e cloud)
- [x] Grafana com dashboards pré-configurados
- [x] Alertas configurados
- [x] Métricas:
  - Hardware: CPU, memória, disco, temperatura
  - Aplicação: requests, latência
  - RFID: leituras/segundo, TAGs únicas, RSSI, antenas

### Documentação
- [x] `README.md` - Visão geral do projeto
- [x] `docs/LOCAL_INSTALL.md` - Guia completo instalação Raspberry Pi (~490 linhas)
- [x] `docs/CLOUD_INSTALL.md` - Guia completo instalação cloud (~670 linhas)
- [x] `CHANGELOG.md` - Histórico de versões

### Banco de Dados
- [x] MongoDB Atlas (cloud gratuito) - substitui MongoDB local
- [x] InfluxDB para time-series (cloud)
- [x] PostgreSQL para metadata (cloud)

## Estrutura de Arquivos
```
rfid-cm710-4-iot/
├── local/              # Deploy Raspberry Pi
├── cloud/              # Deploy Cloud
├── services/           # Serviços Docker
├── docs/               # Documentação
├── rfid_scripts/       # Scripts RFID
├── .github/workflows/  # CI/CD
└── README.md
```

## Próximos Passos (Backlog)
- P1: Adicionar SSL/HTTPS automático com Let's Encrypt
- P1: Configurar alertas por email/Slack
- P2: Dashboard mobile-friendly
- P2: Auto-discovery de dispositivos
- P3: Histórico de leituras com retenção configurável

## Data
- Criado: 26/01/2026
- Última atualização: 26/01/2026
