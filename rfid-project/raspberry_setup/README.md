# 🔧 GUIA DE CONFIGURAÇÃO - Raspberry Pi para Cliente

## ⚠️ EXECUTAR APENAS UMA VEZ ANTES DE ENTREGAR AO CLIENTE

Este guia explica como configurar o Raspberry Pi para funcionar **sem manutenção** na rede do cliente.

---

## 📋 Pré-requisitos

- Raspberry Pi 4 com Raspberry Pi OS instalado
- Módulo CM710-4 conectado via USB
- Acesso à internet (apenas para setup inicial)
- IP/hostname do servidor cloud configurado

---

## 🚀 Setup em 3 Passos

### 1️⃣ Editar Configuração

```bash
cd /app/raspberry_setup
nano setup_raspberry.sh
```

**Editar linha 18:**
```bash
CLOUD_SERVER_IP="seu-servidor-cloud.com"  # ← MUDAR AQUI
```

Colocar IP ou hostname do servidor na nuvem.

**Exemplo:**
```bash
CLOUD_SERVER_IP="192.168.1.200"
# ou
CLOUD_SERVER_IP="rfid.meuservidor.com"
```

Salvar (Ctrl+O) e sair (Ctrl+X).

### 2️⃣ Executar Setup

```bash
chmod +x setup_raspberry.sh
sudo ./setup_raspberry.sh
```

O script vai:
- ✅ Instalar todas as dependências
- ✅ Configurar Docker sem .env
- ✅ Criar serviço systemd
- ✅ Iniciar RabbitMQ local
- ✅ Configurar producer dual-mode

### 3️⃣ Iniciar Leitura RFID

```bash
sudo systemctl start rfid-reader
```

Verificar:
```bash
# Ver logs do reader
sudo journalctl -u rfid-reader -f

# Ver logs do producer
docker logs -f rfid_producer

# Ver leituras
tail -f /home/cpcon/cm710-4/cm710-4.log
```

---

## ✅ Validação

### Status esperado:

**RFID Reader:**
```
Conectado em /dev/ttyUSB0 – leitura ativa
📡 MAC detectado: D8:3A:DD:B3:E0:7F
2026-01-08 12:15:06.189 D8:3A:DD:B3:E0:7F AB301925 1 -29.6
```

**Producer:**
```
✅ RabbitMQ LOCAL conectado: rabbitmq
✅ RabbitMQ CLOUD conectado: 192.168.1.200
✅ MongoDB conectado: mongodb://localhost:27017
📊 EPC=AB301925 | ✅ Local | ✅ Cloud | ✅ Mongo
```

---

## 🔄 Funcionamento Dual-Mode

### Modo Normal (Internet OK)
```
RFID Reader → Log → Producer → {
    ├─ RabbitMQ Local    ✅
    ├─ RabbitMQ Cloud    ✅
    └─ MongoDB Local     ✅
}
```

### Modo Offline (Internet Caiu)
```
RFID Reader → Log → Producer → {
    ├─ RabbitMQ Local    ✅
    ├─ RabbitMQ Cloud    ⚠️ (retry a cada 1min)
    └─ MongoDB Local     ✅
}
```

**Quando internet volta:**
- ✅ Auto-reconecta ao cloud
- ✅ Mensagens locais são processadas
- ✅ Zero intervenção necessária

---

## 🎯 Características do Sistema

### ✅ Zero Manutenção
- Tudo configurado em setup inicial
- Auto-start no boot
- Auto-recovery de falhas
- Logs rotativos automáticos

### ✅ Resiliente
- Funciona sem internet
- Backup local (MongoDB)
- Fila local (RabbitMQ)
- Auto-reconexão cloud

### ✅ Monitorado
- Logs estruturados
- Status via journalctl
- Métricas no Grafana (cloud)
- Alertas configuráveis

---

## 🛠️ Comandos Úteis (Diagnóstico)

### Ver Status Geral
```bash
# Serviço RFID Reader
sudo systemctl status rfid-reader

# Docker containers
docker ps

# Logs do reader
sudo journalctl -u rfid-reader -f

# Logs do producer
docker logs -f rfid_producer --tail 100

# Últimas leituras
tail -n 50 /home/cpcon/cm710-4/cm710-4.log
```

### Reiniciar Serviços
```bash
# Reiniciar RFID reader
sudo systemctl restart rfid-reader

# Reiniciar producer
docker restart rfid_producer

# Reiniciar tudo
sudo systemctl restart rfid-reader
docker-compose -f /app/docker/docker-compose.yml restart
```

### Ver Uso de Recursos
```bash
# CPU/RAM
top

# Docker stats
docker stats

# Espaço em disco
df -h
```

---

## 📊 Monitoramento na Nuvem

### Dashboard Grafana vai mostrar:

1. **Device Status**
   - Online/Offline
   - Última leitura
   - Latência

2. **Leituras**
   - Por segundo
   - TAGs únicas
   - RSSI médio

3. **Health**
   - Conexão RabbitMQ
   - Temperatura CPU
   - Uso de disco

4. **Alertas**
   - Device offline >5min
   - Erro de conexão
   - RSSI muito baixo

---

## 🔐 Segurança

### Credenciais Hardcoded:
```yaml
RABBITMQ_USER: rfid_user
RABBITMQ_PASSWORD: rfid_password
```

**Em produção:**
- Trocar senhas na nuvem E no setup
- Manter senhas sincronizadas
- Não expor porta 5672 publicamente

### Firewall do Cliente:
```
Apenas SAÍDA necessária:
- Porta 5672 (RabbitMQ) → Servidor Cloud
- Porta 443 (HTTPS) → Atualizações
```

---

## 🚨 Troubleshooting

### Reader não inicia
```bash
# Verificar USB
ls -l /dev/ttyUSB* /dev/ttyACM*

# Permissões
sudo usermod -aG dialout cpcon
sudo chmod 666 /dev/ttyUSB0

# Reiniciar
sudo systemctl restart rfid-reader
```

### Producer não conecta cloud
```bash
# Ver logs
docker logs rfid_producer

# Testar conectividade
telnet SERVIDOR-CLOUD-IP 5672

# Verificar config
docker exec rfid_producer env | grep CLOUD
```

### MongoDB local cheio
```bash
# Ver tamanho
du -sh /var/lib/mongodb

# Limpar dados antigos (>30 dias)
mongo rfid_db --eval "db.rfid_readings.deleteMany({timestamp: {\$lt: new Date(Date.now() - 30*24*60*60*1000)}})"
```

---

## 📦 Entregar ao Cliente

### Checklist antes da entrega:

- [ ] Setup executado com sucesso
- [ ] RFID reader funcionando
- [ ] Producer conectado ao cloud
- [ ] Logs aparecendo normalmente
- [ ] Teste de leitura OK
- [ ] Teste de offline/online OK
- [ ] Documentação entregue

### Arquivos no Raspberry:

```
/app/
├── rfid_scripts/
│   ├── rfid_reader.py       # Script de leitura
│   ├── check_config.py      # Verificar config módulo
│   └── set_config.py        # Configurar módulo
├── docker/
│   └── docker-compose.yml   # Orquestração (SEM .env)
├── producer/
│   ├── producer.py          # Producer dual-mode
│   └── Dockerfile
└── raspberry_setup/
    ├── setup_raspberry.sh   # Setup inicial (já executado)
    └── README.md            # Este documento

/home/cpcon/cm710-4/
└── cm710-4.log              # Leituras RFID

/etc/systemd/system/
└── rfid-reader.service      # Serviço systemd
```

---

## 📞 Suporte Pós-Entrega

### Cliente NÃO precisa:
- ❌ Editar arquivos
- ❌ Executar comandos
- ❌ Configurar nada
- ❌ Fazer manutenção

### Cliente PODE:
- ✅ Reiniciar Raspberry (plug/unplug)
- ✅ Ver status no Grafana (cloud)
- ✅ Receber alertas automáticos

### Se houver problema:
1. ✅ Alertas aparecem no Grafana
2. ✅ Logs são enviados à nuvem
3. ✅ Diagnóstico remoto possível
4. ✅ Sistema continua funcionando offline

---

**Sistema 100% autônomo e pronto para produção!** 🚀
