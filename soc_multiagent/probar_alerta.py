"""
Envía una alerta al SOC directamente, sin web ni API.
El supervisor la analiza y el notification_agent manda el email.

Uso:
    python probar_alerta.py                 (usa alerta_ejemplo.json)
    python probar_alerta.py alerta_verdadero_positivo.json
    python probar_alerta.py alerta_falso_positivo.json
"""

import json
import os
import sys

# Trabajar en esta carpeta: aquí están .env, credenciales, token y las alertas JSON
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import config
from supervisor import process_security_alert

# Para que la consola de Windows muestre bien tildes y emojis
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

fichero = sys.argv[1] if len(sys.argv) > 1 else "alerta_ejemplo.json"
with open(fichero, encoding="utf-8") as f:
    alerta = json.load(f)

contexto = {"email_recipient": config.SOC_EMAIL_RECIPIENT} if config.SOC_EMAIL_RECIPIENT else None
resultado = process_security_alert(alerta, alerta.get("id", "ALERT-TEST"), contexto)

print("\nEstado:", resultado["status"])
if resultado["status"] == "error":
    print("Error:", resultado["error"])
else:
    print("Email:", resultado["notification_sent"])
