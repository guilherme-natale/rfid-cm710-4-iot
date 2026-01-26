# 📡 RFID CM710-4 IoT System

Sistema completo de gerenciamento RFID para Raspberry Pi com módulo Chainway CM710-4.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │   Cloud API      │    │    MongoDB       │    │   RabbitMQ       │       │
│  │   (FastAPI)      │    │   (Database)     │    │   (Messaging)    │       │
│  │                  │    │                  │    │                  │       │
│  │  • Auth (JWT)    │    │  • Devices       │    │  • RFID Events   │       │
│  │  • Config Mgmt   │    │  • Readings      │    │  • Real-time     │       │
│  │  • Device Mgmt   │    │  • Configs       │    │                  │       │
│  │  • Statistics    │    │  • Tokens        │    │                  │       │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘       │
│           │                                               ▲                  │
│           │              HTTPS / JWT Auth                 │                  │
│           └───────────────────┬───────────────────────────┘                  │
│                               │                                              │
└───────────────────────────────┼──────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │       Internet        │
                    └───────────┬───────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────────────┐
│                               │           LOCAL (Raspberry Pi)               │
├───────────────────────────────┼──────────────────────────────────────────────┤
│                               │                                              │
│                               ▼                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │   Device Agent   │    │   RFID Reader    │    │   Module CM710-4 │       │
│  │                  │    │   (Python)       │    │   (Hardware)     │       │
│  │  • Auth          │◄───│                  │◄───│                  │       │
│  │  • Config Fetch  │    │  • GPIO Control  │    │  • USB Serial    │       │
│  │  • RabbitMQ Pub  │    │  • Log Writer    │    │  • 4 Antennas    │       │
│  │  • Offline Cache │    │  • Buzzer        │    │                  │       │
│  │  • Heartbeat     │    │                  │    │                  │       │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘       │
│                                                                              │
│  ⚠️  SEM .env NO DISPOSITIVO - Configuração 100% da Cloud                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Estrutura do Projeto

```
rfid-cm710-4-iot/
├── cloud/                      # 🌐 Componentes Cloud
│   ├── api/                    # API REST (FastAPI)
│   │   └── main.py            # Endpoints principais
│   ├── models/                 # Modelos de dados
│   ├── services/              # Serviços auxiliares
│   └── scripts/               # Scripts de deploy cloud
│
├── local/                      # 🏠 Componentes Local (Raspberry Pi)
│   ├── agent/                 # Agente do dispositivo
│   │   └── device_agent.py   # Main agent (NO .env!)
│   ├── scripts/               # Scripts de instalação
│   │   ├── install.sh        # Instalação do sistema
│   │   ├── bootstrap.sh      # Provisionamento do device
│   │   └── start.sh          # Iniciar serviços
│   └── services/              # Arquivos systemd
│       ├── rfid-reader.service
│       └── rfid-agent.service
│
├── docs/                       # 📚 Documentação
│   ├── cloud/                 # Docs da cloud
│   │   ├── ARCHITECTURE.md
│   │   ├── API.md
│   │   └── DEPLOYMENT.md
│   ├── local/                 # Docs do local
│   │   ├── SETUP.md
│   │   ├── BOOTSTRAP.md
│   │   └── TROUBLESHOOTING.md
│   └── assets/                # Screenshots e diagramas
│
└── README.md                   # Este arquivo
```

## 🔐 Modelo de Segurança

### Princípios Fundamentais

1. **Zero Secrets Locais**: Nenhuma credencial sensível armazenada no Raspberry Pi
2. **Cloud como Fonte Única**: Toda configuração vem da Cloud via API segura
3. **JWT com Rotação**: Tokens de curta duração com refresh automático
4. **Revogação Remota**: Dispositivos podem ser desabilitados instantaneamente

### Fluxo de Autenticação

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Bootstrap  │     │   Device    │     │    Cloud    │
│   (1x)      │     │   Agent     │     │    API      │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       │ 1. Register       │                    │
       │──────────────────────────────────────►│
       │                   │                    │
       │ 2. device_id      │                    │
       │◄──────────────────────────────────────│
       │                   │                    │
       │ 3. Save /etc/rfid/device_id           │
       │──────┐            │                    │
       │      │            │                    │
       │◄─────┘            │                    │
       │                   │                    │
       │                   │ 4. Auth(device_id) │
       │                   │───────────────────►│
       │                   │                    │
       │                   │ 5. JWT Token       │
       │                   │◄───────────────────│
       │                   │                    │
       │                   │ 6. GET /config     │
       │                   │───────────────────►│
       │                   │                    │
       │                   │ 7. Config (in mem) │
       │                   │◄───────────────────│
       │                   │                    │
       │                   │ 8. Heartbeat/Data  │
       │                   │───────────────────►│
       │                   │                    │
```

## 🚀 Quick Start

### Cloud (Servidor)

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis
export MONGO_URL="mongodb://localhost:27017"
export JWT_SECRET="$(openssl rand -hex 32)"
export ADMIN_API_KEY="$(openssl rand -hex 32)"

# 3. Iniciar API
python cloud/api/main.py
```

### Local (Raspberry Pi)

```bash
# 1. Instalar sistema
./local/scripts/install.sh

# 2. Provisionar dispositivo (apenas 1x)
RFID_CLOUD_URL="https://your-cloud.com" \
RFID_ADMIN_KEY="your-admin-key" \
./local/scripts/bootstrap.sh

# 3. Iniciar agente
sudo systemctl start rfid-agent
```

## 📡 API Endpoints

### Autenticação
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/devices/authenticate` | Autenticar dispositivo |
| POST | `/api/devices/refresh-token` | Renovar token |

### Configuração
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/config` | Obter configuração |

### Leituras RFID
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/readings` | Enviar leituras |
| GET | `/api/readings` | Consultar leituras |

### Administração
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/admin/devices/register` | Registrar dispositivo |
| GET | `/api/admin/devices` | Listar dispositivos |
| POST | `/api/admin/devices/{id}/revoke` | Revogar acesso |
| PUT | `/api/admin/config/{id}` | Atualizar configuração |
| GET | `/api/admin/statistics` | Estatísticas |

## 📊 Monitoramento

### Status do Dispositivo
O agente envia heartbeats periódicos com:
- Temperatura da CPU
- Uso de memória
- Uso de disco
- Uptime
- Status de conexão

### Métricas RFID
- Total de leituras
- EPCs únicos
- Leituras por antena
- RSSI médio

## 🔧 Comportamento Offline

Quando a cloud está indisponível:

1. **Autenticação**: Usa token em cache (até expirar)
2. **Configuração**: Usa config em cache local (criptografado)
3. **Leituras**: Armazena localmente até 10.000 leituras
4. **Reconexão**: Tenta reconectar automaticamente a cada 60s
5. **Sincronização**: Envia dados cacheados quando online

## 🛡️ Boas Práticas

### Produção
- [ ] Use HTTPS com certificado válido
- [ ] Configure firewall (ufw)
- [ ] Altere todas as senhas padrão
- [ ] Habilite rotação de logs
- [ ] Configure backups do MongoDB
- [ ] Monitore espaço em disco

### Segurança
- [ ] Nunca versione `.env` com segredos
- [ ] Use secrets manager em produção
- [ ] Revogue dispositivos inativos
- [ ] Audite acessos regularmente

## 📝 Licença

MIT License

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-func`)
3. Commit (`git commit -m 'Add nova func'`)
4. Push (`git push origin feature/nova-func`)
5. Abra um Pull Request

---

**Desenvolvido para Raspberry Pi 4 + Chainway CM710-4**
