import os
import requests
import time
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================================
# 🔐 CONFIGURACIONES
# ==========================================================
TOKEN = "8945361217:AAGEDXJq81j4HHgyw1RixJCv8LSKX_wZCqE"
CHAT_ID = "1211460026"
ARCHIVO_DATOS = "datos_bot.json"
LIMITE_DIARIO = 3
TIEMPO_ESPERA = 3600 

# ==========================================================
# 🌍 SERVIDOR WEB PARA MANTENER EL BOT VIVO
# ==========================================================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot de trading activo...".encode("utf-8"))
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    servidor = HTTPServer(("0.0.0.0", puerto), DummyServer)
    servidor.serve_forever()

# ==========================================================
# 🛠 FUNCIONES LÓGICAS
# ==========================================================
def obtener_monedas_dinamicas():
    try:
        url = "https://api-futures.kucoin.com/api/v1/contracts/active"
        respuesta = requests.get(url, timeout=10).json()
        if respuesta["code"] == "200000":
            return [c["symbol"] for c in respuesta["data"] if c["symbol"].endswith("USDTM")]
    except: return []
    return []

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1: return None
    subidas = sum(max(precios[i] - precios[i-1], 0) for i in range(len(precios)-periodo, len(precios)))
    bajadas = sum(max(precios[i-1] - precios[i], 0) for i in range(len(precios)-periodo, len(precios)))
    if bajadas == 0: return 100
    rs = (subidas/periodo) / (bajadas/periodo)
    return 100 - (100 / (1.0 + rs))

def crear_senal(rsi, precio_actual):
    targets = [0.005, 0.010, 0.015]
    sl_porcentaje = 0.02
    if rsi < 20: # LONG extremo
        return "LONG", precio_actual * (1 - sl_porcentaje), [precio_actual * (1 + t) for t in targets]
    elif rsi > 80: # SHORT extremo
        return "SHORT", precio_actual * (1 + sl_porcentaje), [precio_actual * (1 - t) for t in targets]
    return None, None, None

# ==========================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ==========================================================
MONEDAS_A_MONITOREAR = obtener_monedas_dinamicas()
HISTORIALES = {coin: [] for coin in MONEDAS_A_MONITOREAR}

def cargar_datos():
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_DATOS, 'r') as f: return json.load(f)
    return {"ultima_alerta": {c: 0 for c in MONEDAS_A_MONITOREAR}, "contador": 0, "fecha": time.strftime("%Y-%m-%d")}

threading.Thread(target=iniciar_servidor_web, daemon=True).start()

while True:
    datos = cargar_datos()
    hoy = time.strftime("%Y-%m-%d")
    if datos["fecha"] != hoy:
        datos["contador"] = 0
        datos["fecha"] = hoy
    
    if datos["contador"] < LIMITE_DIARIO:
        for coin in MONEDAS_A_MONITOREAR:
            try:
                ticker = requests.get(f"https://api-futures.kucoin.com/api/v1/ticker?symbol={coin}", timeout=5).json()
                if ticker.get("code") == "200000" and ticker.get("data"):
                    precio = float(ticker['data']['price'])
                    HISTORIALES[coin].append(precio)
                    if len(HISTORIALES[coin]) > 30: HISTORIALES[coin].pop(0)
                    
                    if len(HISTORIALES[coin]) >= 30:
                        rsi = calcular_rsi(HISTORIALES[coin])
                        if rsi is not None and (rsi < 20 or rsi > 80):
                            direccion, sl, tp_lista = crear_senal(rsi, precio)
                            if direccion and (time.time() - datos["ultima_alerta"].get(coin, 0) > TIEMPO_ESPERA):
                                msg = f"🌟 *Señal Premium*\n*{coin}* | {direccion}\nEntry: {precio:.5f}\n✅ T1: {tp_lista[0]:.5f}\n⛔ SL: {sl:.5f}"
                                enviar_telegram(msg)
                                datos["ultima_alerta"][coin] = time.time()
                                datos["contador"] += 1
                                with open(ARCHIVO_DATOS, 'w') as f: json.dump(datos, f)
                                if datos["contador"] >= LIMITE_DIARIO: break
            except: continue
    time.sleep(60)
