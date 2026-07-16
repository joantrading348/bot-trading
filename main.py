import os
import requests
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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
# 🔐 CONFIGURACIONES
# ==========================================================
TOKEN = "8945361217:AAGEDXJq81j4HHgyw1RixJCv8LSKX_wZCqE"
CHAT_ID = "1211460026"

def obtener_monedas_dinamicas():
    try:
        url = "https://api-futures.kucoin.com/api/v1/contracts/active"
        respuesta = requests.get(url).json()
        if respuesta["code"] == "200000":
            return [c["symbol"] for c in respuesta["data"] if c["symbol"].endswith("USDTM")]
    except Exception as e:
        print(f"Error al obtener monedas: {e}")
    return []

MONEDAS_A_MONITOREAR = obtener_monedas_dinamicas()
HISTORIALES = {coin: [] for coin in MONEDAS_A_MONITOREAR}
ultima_alerta = {coin: 0 for coin in MONEDAS_A_MONITOREAR}
TIEMPO_ESPERA = 3600 

# ==========================================================
# 🛠 FUNCIONES DE LÓGICA (ACTUALIZADO)
# ==========================================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        # Usamos parse_mode Markdown para mejor formato
        requests.get(url, params={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1: return None
    subidas = sum(max(precios[i] - precios[i-1], 0) for i in range(len(precios)-periodo, len(precios)))
    bajadas = sum(max(precios[i-1] - precios[i], 0) for i in range(len(precios)-periodo, len(precios)))
    if bajadas == 0: return 100
    rs = (subidas/periodo) / (bajadas/periodo)
    return 100 - (100 / (1.0 + rs))

def crear_senal(rsi, precio_actual):
    # Configuración optimizada para cuenta pequeña (3 Targets)
    targets = [0.005, 0.010, 0.015] # 0.5%, 1.0%, 1.5%
    sl_porcentaje = 0.02 # Stop Loss de 2%
    
    if rsi < 30: # LONG
        tp_precios = [precio_actual * (1 + t) for t in targets]
        sl = precio_actual * (1 - sl_porcentaje)
        return "LONG", sl, tp_precios
    elif rsi > 70: # SHORT
        tp_precios = [precio_actual * (1 - t) for t in targets]
        sl = precio_actual * (1 + sl_porcentaje)
        return "SHORT", sl, tp_precios
    return None, None, None

# ==========================================================
# 🚀 EJECUCIÓN PRINCIPAL (CON AGRUPACIÓN)
# ==========================================================
hilo_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
hilo_web.start()

print(f"🚀 Bot iniciado con {len(MONEDAS_A_MONITOREAR)} monedas.")

while True:
    mensajes_ciclo = []
    
    for coin in MONEDAS_A_MONITOREAR:
        try:
            ticker = requests.get(f"https://api-futures.kucoin.com/api/v1/ticker?symbol={coin}").json()
            if ticker.get("code") == "200000":
                precio = float(ticker['data']['price'])
                HISTORIALES[coin].append(precio)
                if len(HISTORIALES[coin]) > 30: HISTORIALES[coin].pop(0)
                
                rsi = calcular_rsi(HISTORIALES[coin])
                
                if rsi is not None:
                    direccion, sl, tp_lista = crear_senal(rsi, precio)
                    if direccion and (time.time() - ultima_alerta[coin] > TIEMPO_ESPERA):
                        # Formato limpio y profesional
                        msg = (f"📩 *{coin}* | {direccion}\n"
                               f"RSI: {rsi:.2f} | Entry: {precio:.5f}\n"
                               f"✅ T1: {tp_lista[0]:.5f} | T2: {tp_lista[1]:.5f} | T3: {tp_lista[2]:.5f}\n"
                               f"⛔ SL: {sl:.5f}")
                        mensajes_ciclo.append(msg)
                        ultima_alerta[coin] = time.time()
        except Exception:
            pass 
    
    # Enviar resumen único si hay señales
    if mensajes_ciclo:
        mensaje_final = "🚨 *Señales detectadas:*\n\n" + "\n\n".join(mensajes_ciclo)
        enviar_telegram(mensaje_final)
    
    time.sleep(20)
