#!/usr/bin/env python3
# MOSTRA CONFIGURAÇÕES ATUAIS CM710-4 (CORRIGIDO conforme protocolo oficial)
import serial
import time
import RPi.GPIO as GPIO
import glob
import sys
import json

EN_PIN = 18

# Mapeamento para decodificação das respostas de configuração
REGIOES_MAP = {
    "01": "China 920-925 MHz",
    "02": "China 840-845 MHz", 
    "04": "Europa 865-868 MHz",
    "08": "USA 902-928 MHz",
    "16": "Korea",
    "32": "Japan",
    "3C": "Brasil 902-928 MHz",
    "3D": "ETSI Upper",
    "3E": "Australia",
    "40": "Israel",
    "41": "Hong Kong",
    "43": "880-930 MHz",
    "45": "Thailand"
}

ANTENNAS_MAP = {
    0x01: "Só antena 1",
    0x02: "Só antena 2",
    0x04: "Só antena 3",
    0x08: "Só antena 4",
    0x0F: "Todas (1, 2, 3, 4)"
}

def calcular_bcc(dados_hex):
    """
    Calcula o BCC (Block Check Character) usando XOR
    BCC = XOR de: Frame Length + CMD Type + Data
    Não inclui: Frame Header e Frame Trailer
    """
    bcc = 0
    # Converter string hex para bytes e calcular XOR
    for i in range(0, len(dados_hex), 2):
        byte = int(dados_hex[i:i+2], 16)
        bcc ^= byte
    return bcc

def enviar_comando(ser, cmd_hex, cmd_esperado_resp=None):
    """Envia um comando para o módulo e retorna a resposta bruta se for válida."""
    try:
        cmd = bytes.fromhex(cmd_hex)
        ser.write(cmd)
        time.sleep(0.5)
        resp = ser.read(100)
        
        if not (resp and len(resp) >= 8 and resp[:2] == b'\xC8\x8C'):
            return None
            
        if cmd_esperado_resp is not None and resp[4] != cmd_esperado_resp:
            return None

        return resp
    except Exception as e:
        return None

def decodificar_temperatura(ser):
    """Obtém e decodifica a temperatura do módulo"""
    # Get Module Temperature (CMD 0x34)
    # Frame: C8 8C 00 08 34 3C 0D 0A
    # BCC = 00 XOR 08 XOR 34 = 3C
    resp = enviar_comando(ser, "C88C0008343C0D0A", 0x35)
    
    if resp and len(resp) >= 8:
        # Temperatura está em resp[6:8] (2 bytes)
        temp_raw_val = (resp[6] << 8) | resp[7]
        
        # Two's complement para valores negativos
        if temp_raw_val & 0x8000:
            temp_raw_val = -(0x10000 - temp_raw_val)

        temp = temp_raw_val / 100.0
        return temp
    return None

def decodificar_firmware(ser):
    """Obtém e decodifica a versão do firmware"""
    # Get Firmware Version (CMD 0x02)
    # Frame: C8 8C 00 08 02 0A 0D 0A
    # BCC = 00 XOR 08 XOR 02 = 0A
    resp = enviar_comando(ser, "C88C0008020A0D0A", 0x03)
    
    if resp and len(resp) >= 10:
        v1, v2, v3 = resp[7], resp[8], resp[9]
        return f"v{v1}.{v2:02d}.{v3}"
    return None

def decodificar_potencia(ser):
    """Obtém e decodifica a potência de transmissão"""
    # Get Current Device Transmission Power (CMD 0x12)
    # Frame: C8 8C 00 08 12 1A 0D 0A
    # BCC = 00 XOR 08 XOR 12 = 1A
    resp = enviar_comando(ser, "C88C0008121A0D0A", 0x13)
    
    if resp and len(resp) >= 14:
        # Write Power está em resp[9:11]
        pot_raw_val = (resp[9] << 8) | resp[10]
        pot_dbm = pot_raw_val / 100.0
        return pot_dbm
    return None

def decodificar_regiao(ser):
    """Obtém e decodifica a região de frequência"""
    # Get Frequency Band Area (CMD 0x2E)
    # Frame: C8 8C 00 08 2E 26 0D 0A
    # BCC = 00 XOR 08 XOR 2E = 26
    resp = enviar_comando(ser, "C88C0008 2E260D0A", 0x2F)
    
    if resp and len(resp) >= 7:
        # Região está em resp[6]
        regiao_hex = f"{resp[6]:02X}"
        descricao = REGIOES_MAP.get(regiao_hex, f"Região Desconhecida (0x{regiao_hex})")
        return regiao_hex, descricao
    return None, None

def decodificar_antenas(ser):
    """Obtém e decodifica a máscara de antenas ativas"""
    # Get Current Device Antenna Settings (CMD 0x2A)
    # Frame: C8 8C 00 08 2A 22 0D 0A
    # BCC = 00 XOR 08 XOR 2A = 22
    resp = enviar_comando(ser, "C88C0008 2A220D0A", 0x2B)
    
    if resp and len(resp) >= 9:
        # Máscara está em resp[7] (LSB) e resp[6] (MSB)
        # Para CM710-4, usamos resp[7] (Ant1-Ant8)
        antenna_select_byte = resp[7]
        descricao = ANTENNAS_MAP.get(antenna_select_byte, f"Máscara Personalizada (0x{antenna_select_byte:02X})")
        return antenna_select_byte, descricao
    return None, None

def decodificar_fastid(ser):
    """Obtém e decodifica o status do FastID"""
    # Get FastID Functional Status (CMD 0x5E)
    # Frame: C8 8C 00 0A 5E 00 00 54 0D 0A
    # BCC = 00 XOR 0A XOR 5E XOR 00 XOR 00 = 54
    resp = enviar_comando(ser, "C88C000A5E0000540D0A", 0x5F)
    
    if resp and len(resp) >= 9:
        # resp[7] = OK/Fail, resp[8] = ON/OFF
        if resp[7] == 0x01:  # OK
            status = "Ligado" if resp[8] == 0x01 else "Desligado"
            return status
    return None

def get_config():
    """Obtém todas as configurações e retorna como JSON"""
    config = {}
    
    # Inicialização do GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(EN_PIN, GPIO.OUT)
    GPIO.output(EN_PIN, GPIO.HIGH)
    time.sleep(2.0)
    
    # Busca e abre a porta serial
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    if not ports:
        return {"error": "Nenhuma porta encontrada"}
    
    try:
        ser = serial.Serial(ports[0], 115200, timeout=1.0)
        ser.reset_input_buffer()
    except Exception as e:
        GPIO.cleanup()
        return {"error": f"Erro ao abrir porta: {e}"}
    
    # Firmware
    firmware = decodificar_firmware(ser)
    if firmware:
        config['firmware'] = firmware
    
    # Temperatura
    temp = decodificar_temperatura(ser)
    if temp is not None:
        config['temperatura'] = temp
    
    # Potência
    pot = decodificar_potencia(ser)
    if pot is not None:
        config['potencia'] = pot
    
    # Região
    regiao_hex, regiao_desc = decodificar_regiao(ser)
    if regiao_hex:
        config['regiao'] = regiao_hex
        config['regiao_desc'] = regiao_desc
    
    # Antenas
    ant_mask, ant_desc = decodificar_antenas(ser)
    if ant_mask is not None:
        config['antenas'] = ant_mask
        config['antenas_desc'] = ant_desc
    
    # FastID
    fastid = decodificar_fastid(ser)
    if fastid:
        config['fastid'] = fastid
    
    # Parar inventário (CMD 0x84 é o comando STOP, não 0x8C)
    # Stop Continuous Inventory Tag (CMD 0x8C)
    # Frame: C8 8C 00 08 8C 84 0D 0A
    # BCC = 00 XOR 08 XOR 8C = 84
    try:
        ser.write(bytes.fromhex("C88C00088C840D0A"))
        time.sleep(0.2)
        ser.close()
    except:
        pass
    
    GPIO.output(EN_PIN, GPIO.LOW)
    GPIO.cleanup()
    
    return config

if __name__ == "__main__":
    config = get_config()
    print(json.dumps(config, indent=2))
