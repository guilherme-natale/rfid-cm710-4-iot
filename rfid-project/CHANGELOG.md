# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [2.0.0] - 2026-01-26

### Adicionado
- **Docker Compose completo** para ambiente LOCAL (Raspberry Pi)
- **Docker Compose completo** para ambiente CLOUD (DigitalOcean/Contabo)
- **CI/CD Pipeline** com GitHub Actions (deploy em tags de release)
- **Prometheus** para coleta de métricas
- **Grafana** com dashboards pré-configurados:
  - Métricas de hardware (CPU, memória, disco, temperatura)
  - Métricas de aplicação (requests, latência)
  - Métricas RFID (leituras/segundo, TAGs únicas, RSSI por antena)
- **Node Exporter** para métricas de sistema
- **cAdvisor** para métricas de containers (cloud)
- **Alertas** configurados no Prometheus
- **Documentação completa** separada:
  - `docs/LOCAL_INSTALL.md` - Guia de instalação no Raspberry Pi
  - `docs/CLOUD_INSTALL.md` - Guia de instalação na cloud
- **Nginx reverse proxy** (opcional) com suporte a SSL
- **PostgreSQL** para metadados e configurações
- **InfluxDB** para armazenamento time-series

### Alterado
- Removido MongoDB local - dados agora vão para MongoDB Atlas (cloud gratuito)
- Producer atualizado com métricas Prometheus
- Consumer atualizado com métricas Prometheus
- Backend atualizado para suportar MongoDB Atlas
- Estrutura de diretórios reorganizada:
  - `local/` - Configurações para Raspberry Pi
  - `cloud/` - Configurações para servidor cloud
  - `services/` - Serviços Docker compartilhados
  - `docs/` - Documentação

### Removido
- Docker compose antigo em `/docker`
- MongoDB local (substituído por MongoDB Atlas)
- Arquivos de documentação duplicados

## [1.0.0] - 2026-01-08

### Adicionado
- Sistema inicial de rastreamento RFID
- Suporte ao módulo Chainway CM710-4
- Interface web React
- Backend FastAPI
- RabbitMQ para mensageria
- MongoDB local para armazenamento
