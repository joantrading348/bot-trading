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

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    servidor = HTTPServer(("0.0.0.0", puerto), DummyServer)
    servidor.serve_forever()

# ==========================================================
# 🔐 CONFIGURACIONES
# ==========================================================
API_KEY = os.environ.get("KC-API-KEY")
API_SECRET = os.environ.get("API_SECRET")
API_PASSPHRASE = os.environ.get("API_PASSPHRASE")

TOKEN = "8945361217:AAGEDXJq81j4HHgyw1RixJCv8LSKX_wZCqE"
CHAT_ID = "1211460026"

MONEDAS_A_MONITOREAR = [
    'DOGEUSDTM', 'SOLUSDTM', 'PEPEUSDTM', 'SHIBUSDTM', 
    'WIFUSDTM', 'BONKUSDTM', 'XRPUSDTM', 'ADAUSDTM',
    'ETHUSDTM', 'XBTUSDTM', 'AVAXUSDTM', 'NEARUSDTM'
]

HISTORIALES = {coin: [] for coin in MONEDAS_A_MONITOREAR}

# ==========================================================
# 🛠 FUNCIONES DE LÓGICA
# ==========================================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": CHAT_ID, "text": mensaje})
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1: return None
    subidas = sum(max(precios[i] - precios[i-1], 0) for i in range(len(precios)-periodo, len(precios)))
    bajadas = sum(max(precios[i-1] - precios[i], 0) for i in range(len(precios)-periodo, len(precios)))
    if bajadas == 0: return 100
    rs = (subidas/periodo) / (bajadas/periodo)
    return 100 - (100 / (1.0 + rs))

def crear_senal(rsi):
    # Configuración optimizada: SL 5% y 2 Targets (5% y 10%)
    if rsi < 30:
        return "LONG", 0.05, [0.05, 0.10]
    elif rsi > 70:
        return "SHORT", 0.05, [0.05, 0.10]
    return None, None, None

# ==========================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ==========================================================
hilo_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
hilo_web.start()

print("🚀 Bot iniciado correctamente.")

while True:
    for coin in MONEDAS_A_MONITOREAR:
        try:
            ticker = requests.get(f"https://api-futures.kucoin.com/api/v1/ticker?symbol={coin}").json()
            if ticker.get("code") == "200000":
                precio = float(ticker['data']['price'])
                HISTORIALES[coin].append(precio)
                if len(HISTORIALES[coin]) > 30: HISTORIALES[coin].pop(0)
                
                rsi = calcular_rsi(HISTORIALES[coin])
                print(f"Moneda: {coin} | Precio: {precio} | RSI: {rsi}")
                
                if rsi is not None:
                    direccion, sl, tp = crear_senal(rsi)
                    if direccion:
                        mensaje = f"📈 Señal detectada: {coin}\nDirección: {direccion}\nRSI: {rsi:.2f}\nStop Loss: {sl*100}%\nTargets: {tp}"
                        enviar_telegram(mensaje)
                        # Aquí añadirías tu lógica de ejecución en KuCoin
        except Exception as e:
            print(f"Error procesando {coin}: {e}")
    
    time.sleep(15)
