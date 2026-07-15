import os
import time
import ccxt
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. MINI SERVIDOR WEB PARA ENGAÑAR A RENDER ---
# Esto hace que Render vea un puerto abierto y mantenga tu bot corriendo gratis.
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot de Trading Activo")

def run_server():
    # Render asigna automáticamente un puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    print(f"Servidor de control iniciado en el puerto {port}")
    server.serve_forever()

# Iniciar el servidor web en un hilo separado para no interferir con el bot
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()


# --- 2. CONFIGURACIÓN DEL BOT DE TRADING ---
api_key = os.getenv('KUCOIN_API_KEY', 'TU_API_KEY_AQUI')
secret = os.getenv('KUCOIN_SECRET', 'TU_SECRET_AQUI')
password = os.getenv('KUCOIN_PASSWORD', 'TU_PASSWORD_AQUI')

exchange = ccxt.kucoin({
    'apiKey': api_key,
    'secret': secret,
    'password': password,
    'enableRateLimit': True,
})

symbol = 'BTC/USDT'
intervalo_segundos = 60

print("¡Bot de trading iniciado exitosamente!")
print(f"Monitoreando el par: {symbol}")

# --- 3. BUCLE PRINCIPAL ---
while True:
    try:
        ticker = exchange.fetch_ticker(symbol)
        precio_actual = ticker['last']
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] El precio de {symbol} es: {precio_actual} USDT", flush=True)
        
    except Exception as e:
        print(f"Error en el bot: {e}", flush=True)
    
    time.sleep(intervalo_segundos)
