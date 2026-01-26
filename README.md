# 📡 RFID CM710-4 IoT System

Sistema IoT híbrido para leitores RFID Chainway CM710-4 com Raspberry Pi.

**Arquitetura:** Cloud como fonte única de verdade, zero secrets no dispositivo local.

## 📁 Estrutura do Repositório

```
.
├── cloud/                    # ☁️ Backend Cloud
│   ├── src/                  # Código fonte da API
│   │   ├── main.py          # FastAPI application
│   │   └── server.py        # Entry point
│   ├── docker/              # Docker configs
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── scripts/             # Scripts de instalação
│   │   └── install-cloud.sh
│   ├── requirements.txt
│   └── .env                 # ⚠️ Não versionado
│
├── local/                    # 🏠 Edge (Raspberry Pi)
│   ├── src/                  # Código fonte
│   │   ├── device_agent.py  # Agente principal
│   │   └── rfid_reader.py   # Leitor CM710-4
│   ├── scripts/             # Scripts de instalação
│   │   ├── install.sh
│   │   ├── bootstrap.sh
│   │   └── start.sh
│   ├── config/              # Systemd services
│   │   ├── rfid-agent.service
│   │   └── rfid-reader.service
│   └── requirements.txt
│
├── docs/                     # 📚 Documentação
│   ├── diagrams/            # Diagramas Mermaid
│   ├── screenshots/         # Exemplos de output
│   ├── api/                 # Documentação da API
│   ├── SETUP.md
│   └── TROUBLESHOOTING.md
│
├── README.md                 # Este arquivo
└── .gitignore
```

## 🔐 Modelo de Segurança

| Aspecto | Cloud | Local (Pi) |
|---------|-------|------------|
| Secrets | ✅ JWT_SECRET, DB creds | ❌ Nenhum |
| .env | ✅ Sim | ❌ Proibido |
| Config | Fonte única | Recebe via API |
| Auth | Gera JWT | Valida JWT |

## 🚀 Quick Start

### Cloud (Servidor)

```bash
# Com Docker (recomendado)
cd cloud
./scripts/install-cloud.sh

# Ou manualmente
cd cloud
pip install -r requirements.txt
python src/server.py
```

### Local (Raspberry Pi)

```bash
# 1. Instalar
cd local
./scripts/install.sh

# 2. Provisionar (1x)
RFID_CLOUD_URL="https://seu-server.com" \
RFID_ADMIN_KEY="sua-chave-admin" \
./scripts/bootstrap.sh

# 3. Iniciar
sudo systemctl start rfid-agent
```

## 📊 API Endpoints

| Método | Endpoint | Auth | Descrição |
|--------|----------|------|-----------|
| GET | `/health` | - | Health check |
| POST | `/api/devices/authenticate` | - | Auth device |
| GET | `/api/config` | JWT | Get config |
| POST | `/api/readings` | JWT | Submit readings |
| POST | `/api/heartbeat` | JWT | Heartbeat |
| POST | `/api/admin/devices/register` | Admin | Register device |
| GET | `/api/admin/statistics` | Admin | Statistics |

**Swagger UI:** `http://localhost:8001/docs`

## 📖 Documentação

- [Arquitetura e Diagramas](docs/diagrams/ARCHITECTURE.md)
- [API Reference](docs/api/API.md)
- [Setup Local](docs/SETUP.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Screenshots/Exemplos](docs/screenshots/EXAMPLES.md)

## License

MIT
