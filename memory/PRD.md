# PRD - RFID CM710-4 IoT System

## Original Problem Statement
Refatorar completamente o sistema RFID IoT CM710-4 separando Cloud e Local (Raspberry Pi), implementando configuração 100% centralizada na cloud (sem .env no dispositivo local), autenticação JWT + Device ID, e documentação completa.

## Architecture

### Cloud Component (`/cloud`)
- **FastAPI REST API** - Gerenciamento central de dispositivos e configurações
- **MongoDB** - Armazenamento de dispositivos, leituras, tokens, configs
- **JWT Authentication** - Tokens de curta duração com rotação automática

### Local Component (`/local`)
- **Device Agent** - Comunicação com cloud, cache offline, heartbeat
- **RFID Reader** - Leitura de tags via módulo CM710-4
- **Systemd Services** - Gerenciamento de serviços

## User Personas

1. **Administrador Cloud** - Gerencia dispositivos, revoga acessos, monitora estatísticas
2. **Técnico de Campo** - Instala e provisiona Raspberry Pi com script bootstrap
3. **Sistema Automatizado** - Envia leituras RFID automaticamente para cloud

## Core Requirements (Static)

- [x] Separação clara entre Cloud e Local
- [x] Zero secrets no dispositivo local (sem .env)
- [x] Configuração 100% centralizada na cloud
- [x] JWT com rotação automática
- [x] Revogação remota de dispositivos
- [x] Modo offline com cache local
- [x] Documentação completa

## What's Been Implemented (Jan 2026)

### Cloud API (`/cloud/api/main.py`)
- [x] Health check endpoint
- [x] Device registration (admin)
- [x] Device authentication (JWT)
- [x] Token refresh
- [x] Configuration distribution
- [x] RFID readings submission/query
- [x] Device heartbeat
- [x] Device revocation/reinstatement
- [x] System statistics

### Local Scripts
- [x] `install.sh` - Instalação do sistema
- [x] `bootstrap.sh` - Provisionamento do dispositivo
- [x] `start.sh` - Iniciar agente
- [x] `rfid_reader.py` - Leitura de tags CM710-4
- [x] `device_agent.py` - Agente de comunicação

### Systemd Services
- [x] `rfid-reader.service`
- [x] `rfid-agent.service`

### Documentation
- [x] README.md principal
- [x] `docs/cloud/ARCHITECTURE.md`
- [x] `docs/cloud/API.md`
- [x] `docs/cloud/DEPLOYMENT.md`
- [x] `docs/local/SETUP.md`
- [x] `docs/local/TROUBLESHOOTING.md`

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | - | Health check |
| `/api/devices/authenticate` | POST | - | Device auth |
| `/api/devices/refresh-token` | POST | JWT | Refresh token |
| `/api/config` | GET | JWT | Get config |
| `/api/readings` | POST | JWT | Submit readings |
| `/api/readings` | GET | JWT | Query readings |
| `/api/heartbeat` | POST | JWT | Heartbeat |
| `/api/admin/devices/register` | POST | Admin | Register device |
| `/api/admin/devices` | GET | Admin | List devices |
| `/api/admin/devices/{id}` | GET | Admin | Get device |
| `/api/admin/devices/{id}/revoke` | POST | Admin | Revoke device |
| `/api/admin/devices/{id}/reinstate` | POST | Admin | Reinstate |
| `/api/admin/config/{id}` | PUT | Admin | Update config |
| `/api/admin/statistics` | GET | Admin | Statistics |

## Test Results

- **Backend**: 100% (19/19 tests passed)
- All critical flows working correctly

## Prioritized Backlog

### P0 (Critical) - Done
- [x] Core API endpoints
- [x] Device authentication
- [x] Configuration distribution

### P1 (High Priority) - Future
- [ ] Websocket para real-time readings
- [ ] Dashboard web para admin
- [ ] Métricas Prometheus
- [ ] Alertas via email/Slack

### P2 (Medium Priority) - Future
- [ ] Multi-tenancy
- [ ] Rate limiting
- [ ] API versioning
- [ ] Bulk device registration

### P3 (Low Priority) - Future
- [ ] Mobile app para técnicos
- [ ] Grafana dashboards
- [ ] Integração com ERPs

## Security Considerations

1. No .env files on devices
2. JWT tokens expire in 24h
3. Admin API key required for management
4. Device revocation is immediate
5. Config cached only in memory or encrypted file

## Next Tasks

1. Deploy para servidor de produção
2. Configurar HTTPS com Let's Encrypt
3. Provisionar primeiro Raspberry Pi de teste
4. Implementar monitoramento com Prometheus
