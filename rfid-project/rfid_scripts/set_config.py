#!/usr/bin/env python3
# CONFIGURADOR CM710-4 (CORRIGIDO conforme protocolo oficial)
import serial
import time
import RPi.GPIO as GPIO
import glob
import sys
import json

EN_PIN = 18

def calcular_bcc(dados_hex):
    """
    Calcula o BCC (Block Check Character) usando XOR
    BCC = XOR de: Frame Length + CMD Type + Data
    """
    bcc = 0
    for i in range(0, len(dados_hex), 2):
        byte = int(dados_hex[i:i+2], 16)
        bcc ^= byte
    return bcc

def enviar_comando(ser, cmd_hex):
    """Envia um comando para o módulo CM710-4 e processa a resposta."""
    try:
        cmd = bytes.fromhex(cmd_hex)
        ser.write(cmd)
        time.sleep(0.5)
        resp = ser.read(100)
        if resp and len(resp) >= 8 and resp[:2] == b'\xC8\x8C':
            return {"success": True, "response": resp.hex().upper()}
        else:
            return {"success": False, "error": "sem resposta ou erro"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_config(config):
    """
    Configura o módulo CM710-4
    config = {
        "potencia": 20,  # 5-30 dBm
        "regiao": "3C",  # Código da região (hex)
        "antenas": "0F",  # Máscara de antenas (hex): 01, 02, 04, 08, 0F
        "frequencia": None,  # None = hopping, ou valor em kHz
        "fastid": "01"  # 01 = ligado, 00 = desligado
    }
    """
    result = {}
    
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
    
    # 1) Potência (CMD 0x10)
    # Set Transmit Power
    # Data: Status (1) + Antenna Number (1) + Read Power (2) + Write Power (2)
    if 'potencia' in config:
        dbm = int(config['potencia'])
        if not 5 <= dbm <= 30:
            dbm = 20
        
        pot_val = dbm * 100
        pot_hex = f"{pot_val:04X}"
        
        # Status=0x02 (save), Antenna=0x01, Read=Write Power
        dados = f"000E100201{pot_hex}{pot_hex}"
        bcc = calcular_bcc(dados)
        cmd_power = f"C88C{dados}{bcc:02X}0D0A"
        result['potencia'] = enviar_comando(ser, cmd_power)
    
    # 2) Região (CMD 0x2C)
    # Frequency Band Area Settings
    # Data: Save Settings Logo (1) + Logo DByte0 (1)
    if 'regiao' in config:
        regiao_hex = config['regiao']
        
        # Save=0x01, Region code
        dados = f"000A2C01{regiao_hex}"
        bcc = calcular_bcc(dados)
        cmd_regiao = f"C88C{dados}{bcc:02X}0D0A"
        result['regiao'] = enviar_comando(ser, cmd_regiao)
    
    # 3) Antenas (CMD 0x28)
    # Antenna Settings
    # Data: DByte2 (save) + DByte1 (Ant16-9) + DByte0 (Ant8-1)
    if 'antenas' in config:
        ant_mask = int(config['antenas'], 16)
        
        # DByte2=0x01 (save), DByte1=0x00, DByte0=ant_mask
        dados = f"000B28010{ant_mask:02X}"
        bcc = calcular_bcc(dados)
        cmd_ant = f"C88C{dados}{bcc:02X}0D0A"
        result['antenas'] = enviar_comando(ser, cmd_ant)
    
    # 4) Frequência fixa (CMD 0x14)
    # Fixed Frequency Setting
    # Data: Fixed frequency channel Number (1) + Freq (3 bytes)
    if 'frequencia' in config and config['frequencia']:
        freq = int(config['frequencia'])
        if 840000 <= freq <= 928000:
            # Converter frequência para 3 bytes (little-endian)
            b0 = freq & 0xFF
            b1 = (freq >> 8) & 0xFF
            b2 = (freq >> 16) & 0xFF
            
            # Channel count=0x01, Frequency (3 bytes)
            dados = f"000C1401{b2:02X}{b1:02X}{b0:02X}"
            bcc = calcular_bcc(dados)
            cmd_freq = f"C88C{dados}{bcc:02X}0D0A"
            result['frequencia'] = enviar_comando(ser, cmd_freq)
    
    # 5) FastID (CMD 0x5C)
    # Setting up FastID Feature
    # Data: ON/OFF (1) + Rev (1)
    if 'fastid' in config:
        fastid_val = config['fastid']
        
        # ON/OFF + Reserved byte (0x00)
        dados = f"000A5C{fastid_val}00"
        bcc = calcular_bcc(dados)
        cmd_fast = f"C88C{dados}{bcc:02X}0D0A"
        result['fastid'] = enviar_comando(ser, cmd_fast)
    
    # Finalização - Stop Inventory
    # Stop Continuous Inventory Tag (CMD 0x8C)
    # Frame: C8 8C 00 08 8C 84 0D 0A
    try:
        ser.write(bytes.fromhex("C88C00088C840D0A"))
        time.sleep(0.2)
        ser.close()
    except:
        pass
    
    GPIO.output(EN_PIN, GPIO.LOW)
    GPIO.cleanup()
    
    return result

if __name__ == "__main__":
    if len(sys.argv) > 1:
        config = json.loads(sys.argv[1])
        result = set_config(config)
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"error": "Config JSON required"}, indent=2))
