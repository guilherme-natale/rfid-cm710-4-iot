#!/usr/bin/env python3
import serial
import time
import RPi.GPIO as GPIO
import glob
import sys
from datetime import datetime
import uuid

EN_PIN = 18
BUZZER_PIN = 17
LOG_FILE = "/var/log/cm710-4.log"

def get_mac():
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 48, 8)][::-1]).upper()
        return mac
    except:
        return "00:00:00:00:00:00"

MAC_ADDRESS = get_mac()

JA_PAROU = False

def sair(signum=None, frame=None):
    global JA_PAROU
    if JA_PAROU:
        return
    JA_PAROU = True
    try:
        # Stop Continuous Inventory Tag (CMD 0x8C)
        # Frame: C8 8C 00 08 8C 84 0D 0A
        # BCC = 00 XOR 08 XOR 8C = 84
        ser.write(bytes.fromhex("C88C00088C840D0A"))
        time.sleep(0.1)
        ser.close()
    except:
        pass
    try:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.output(EN_PIN, GPIO.LOW)
        GPIO.cleanup()
    except:
        pass
    sys.exit(0)

# ==================== INÍCIO ====================
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(EN_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(EN_PIN, GPIO.HIGH)
GPIO.output(BUZZER_PIN, GPIO.LOW)
time.sleep(2.0)

ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
if not ports:
    print("Nenhuma porta encontrada!")
    sys.exit(1)

ser = serial.Serial(ports[0], 115200, timeout=1.0)
print(f"Conectado em {ports[0]} – leitura ativa")
ser.reset_input_buffer()

# Continuous Inventory Label Command (0x82)
# Frame: C8 8C 00 0A 82 00 00 88 0D 0A
# BCC = 00 XOR 0A XOR 82 XOR 00 XOR 00 = 88
ser.write(bytes.fromhex("C88C000A820000880D0A"))
time.sleep(0.5)

buffer = b""

def registrar(epc, ant, rssi):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    linha = f"{ts} {MAC_ADDRESS} {epc} {ant} {rssi:6.1f}"
    print(linha)
    with open(LOG_FILE, "a") as f:
        f.write(linha + "\n")
    
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.01)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

import signal
signal.signal(signal.SIGINT, sair)
signal.signal(signal.SIGTERM, sair)

try:
    while True:
        if ser.in_waiting:
            buffer += ser.read(ser.in_waiting)
        while b'\x0D\x0A' in buffer:
            pos = buffer.find(b'\x0D\x0A')
            if pos < 10:
                buffer = buffer[pos+2:]
                continue
            frame = buffer[:pos+2]
            buffer = buffer[pos+2:]
            if len(frame) < 12 or frame[:2] != b'\xC8\x8C' or frame[4] != 0x83:
                continue
            i = 5
            pc = frame[i] << 8 | frame[i+1]
            epc_len = ((pc >> 11) & 0x1F) * 2
            i += 2
            epc = frame[i:i+epc_len].hex().upper()
            i += epc_len
            rssi_raw = frame[i] << 8 | frame[i+1]
            rssi = (rssi_raw - 65536)/10.0 if rssi_raw > 32767 else rssi_raw/10.0
            i += 2
            ant = ((frame[i] - 1) % 4) + 1

            if len(epc) == 8:
                registrar(epc, ant, rssi)

except:
    sair()
