import os
import requests
import time
import hmac
import hashlib
import json
import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================================
# 🌍 MINI SERVIDOR WEB PARA ENGAÑAR A RENDER (Evita el error de puertos)
# ==========================================================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot de trading ejecutándose correctamente...".encode("utf-8"))

def iniciar_servidor_web():
    # Render asigna automáticamente un puerto en la variable de entorno PORT
    puerto = int(os.environ.get("PORT", 10000))
    servidor = HTTPServer(("0.0.0.0", puerto), DummyServer)
    print(f"🌍 Servidor web dummy iniciado en el puerto {puerto}")
    servidor.serve_forever()

# ==========================================================
# 🔐 CREDENCIALES DESDE VARIABLES DE ENTORNO DE RENDER
# ==========================================================
API_KEY = os.environ.get("KC-API-KEY")
API_SECRET = os.environ.get("API_SECRET")
API_PASSPHRASE = os.environ.get("API_PASSPHRASE")

# Parámetros de Riesgo
MONTO_FIJO_USD = 5.0    # Margen por operación ($5 USD)
APALANCAMIENTO = 10     # Apalancamiento (10x)

# Configuración de Telegram
TOKEN = "8945361217:AAGEDXJq81j4HHgyw1RixJCv8LSKX_wZCqE"
CHAT_ID = "1211460026"

MONEDAS_A_MONITOREAR = [
    'DOGE-USDT', 'SOL-USDT', 'PEPE-USDT', 'SHIB-USDT', 
    'WIF-USDT', 'BONK-USDT', 'XRP-USDT', 'ADA-USDT',
    'ETH-USDT', 'BTC-USDT', 'AVAX-USDT', 'NEAR-USDT'
]

HISTORIALES = {coin: [] for coin in MONEDAS_A_MONITOREAR}
ESTADOS_ANTERIORES = {coin: None for coin in MONEDAS_A_MONITOREAR}
CONTRATOS_VALIDOS = {}

# ==========================================================
# ⚡ ENVIAR MENSAJES A TELEGRAM
# ==========================================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": mensaje}
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# ==========================================================
# 📈 CÁLCULOS MATEMÁTICOS Y SEÑALES
# ==========================================================
def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1:
        return None
    subidas = 0
    bajadas = 0
    for i in range(len(precios) - periodo, len(precios)):
        diferencia = precios[i] - precios[i-1]
        if diferencia > 0:
            subidas += diferencia
        else:
            bajadas += abs(diferencia)
    promedio_subidas = subidas / periodo
    promedio_bajadas = bajadas / periodo
    if promedio_bajadas == 0:
        return 100
    rs = promedio_subidas / promedio_bajadas
    return 100 - (100 / (1.0 + rs))

def formatear_precio(valor):
    if valor < 0.0001:
        return f"{valor:.8f}"
    elif valor < 1.0:
        return f"{valor:.5f}"
    else:
        return f"{valor:.4f}"

def crear_senal(coin, direccion, precio):
    porcentaje_sl = 0.02   # 2% de Stop Loss
    porcentaje_tp = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06] # Targets del 1% al 6%

    if direccion == "LONG":
        color_emoji = "🟢"
        stop_loss = precio * (1 - porcentaje_sl)
        targets = [precio * (1 + p) for p in porcentaje_tp]
    else: # SHORT
        color_emoji = "🔴"
        stop_loss = precio * (1 + porcentaje_sl)
        targets = [precio * (1 - p) for p in porcentaje_tp]

    pair_name = coin.replace("-USDT", "USDT")
    
    msg = (
        f"📥 Pair: {pair_name}\n"
        f"📈 {direccion} {color_emoji} Direction: {direccion}\n"
        f"💯 Leverage: {APALANCAMIENTO}x\n\n"
        f"📊 Entry: {formatear_precio(precio)}\n"
        f"❗️ Enter as soonest possible ❗️\n\n"
        f"✅ Target 1: {formatear_precio(targets[0])}\n"
        f"✅ Target 2: {formatear_precio(targets[1])}\n"
        f"✅ Target 3: {formatear_precio(targets[2])}\n"
        f"✅ Target 4: {formatear_precio(targets[3])}\n"
        f"✅ Target 5: {formatear_precio(targets[4])}\n"
        f"✅ Target 6: {formatear_precio(targets[5])}\n\n"
        f"⛔️ Stop Loss: {formatear_precio(stop_loss)}"
    )
    return msg, stop_loss, targets[0]

# ==========================================================
# 🔌 CONEXIÓN DIRECTA CON API FUTUROS DE KUCOIN (Sin Proxy)
# ==========================================================
def kucoin_api_request(endpoint, method="POST", payload=None):
    base_url = "https://api-futures.kucoin.com"
    url = base_url + endpoint
    timestamp = str(int(time.time() * 1000))
    
    body = ""
    if payload:
        body = json.dumps(payload)
        
    str_to_sign = timestamp + method + endpoint + body
    secret_bytes = bytes(API_SECRET, 'utf-8')
    str_bytes = bytes(str_to_sign, 'utf-8')
    signature = hmac.new(secret_bytes, str_bytes, hashlib.sha256).digest()
    
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    passphrase_b64 = base64.b64encode(hmac.new(secret_bytes, bytes(API_PASSPHRASE, 'utf-8'), hashlib.sha256).digest()).decode('utf-8')
    
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature_b64,
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-PASSPHRASE": passphrase_b64,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    
    if method == "POST":
        response = requests.post(url, headers=headers, data=body)
    else:
        response = requests.get(url, headers=headers)
        
    return response.json()

def obtener_posiciones_abiertas():
    try:
        res = kucoin_api_request("/api/v1/positions", "GET")
        if res.get("code") == "200000" and "data" in res:
            posiciones = [p for p in res["data"] if float(p["currentQty"]) != 0]
            return len(posiciones)
    except Exception as e:
        print(f"Error consultando posiciones: {e}")
    return 0

def obtener_detalles_contrato(coin):
    global CONTRATOS_VALIDOS
    if coin in CONTRATOS_VALIDOS:
        return CONTRATOS_VALIDOS[coin]
        
    intentos_simbolos = [
        coin.replace("-", "").replace("USDT", "USDTM"),
        coin.replace("-", "") + "M"
    ]
    
    for symbol in intentos_simbolos:
        try:
            res = requests.get(f"https://api-futures.kucoin.com/api/v1/contracts/{symbol}").json()
            if res.get("code") == "200000" and "data" in res:
                multiplier = float(res['data']['multiplier'])
                CONTRATOS_VALIDOS[coin] = (symbol, multiplier)
                return symbol, multiplier
        except:
            continue
            
    default_symbol = coin.replace("-", "").replace("USDT", "USDTM")
    return default_symbol, 0.01

# ==========================================================
# 📥 EJECUCIÓN DINÁMICA DE OPERACIONES (CROSS/ISOLATED)
# ==========================================================
def ejecutar_orden_futuros(coin, direccion, entry_price, sl_price, tp_price):
    try:
        symbol, multiplier = obtener_detalles_contrato(coin)
        
        # Actualizar apalancamiento en KuCoin
        leverage_payload = {"symbol": symbol, "leverage": str(APALANCAMIENTO)}
        kucoin_api_request("/api/v1/position/update-leverage", "POST", leverage_payload)
        
        # Calcular tamaño en contratos
        valor_total_posicion = MONTO_FIJO_USD * APALANCAMIENTO
        cantidad_contratos = int(round(valor_total_posicion / (entry_price * multiplier)))
        if cantidad_contratos < 1:
            cantidad_contratos = 1
            
        side = 'buy' if direccion == "LONG" else 'sell'
        contra_side = 'sell' if side == 'buy' else 'buy'
        pos_side = 'LONG' if direccion == "LONG" else 'SHORT'
        
        # Probar dinámicamente ambos modos de margen
        modos_a_probar = ["CROSS", "ISOLATED"]
        res_orden = None
        modo_exitoso = None
        
        for modo in modos_a_probar:
            order_payload = {
                "clientOid": str(int(time.time() * 1000)),
                "side": side,
                "symbol": symbol,
                "type": "market",
                "size": cantidad_contratos,
                "leverage": str(APALANCAMIENTO),
                "positionSide": pos_side,
                "marginMode": modo
            }
            res_orden = kucoin_api_request("/api/v1/orders", "POST", order_payload)
            
            if res_orden.get("code") == "200000":
                modo_exitoso = modo
                break
            
            msg_error = res_orden.get("msg", "").lower()
            if "margin mode" not in msg_error:
                break
                
        if modo_exitoso:
            print(f"✅ Entrada {pos_side} Ejecutada con éxito usando modo de margen: {modo_exitoso}.")
        else:
            msg_err = res_orden.get("msg", "Error desconocido") if res_orden else "Sin respuesta"
            raise Exception(f"{msg_err}")
        
        # Programar Stop Loss
        sl_payload = {
            "clientOid": str(int(time.time() * 1000) + 1),
            "side": contra_side,
            "symbol": symbol,
            "type": "market",
            "stop": "down" if side == 'buy' else "up",
            "stopPriceType": "TP",
            "stopPrice": float(formatear_precio(sl_price)),
            "size": cantidad_contratos,
            "positionSide": pos_side,
            "marginMode": modo_exitoso,
            "reduceOnly": True
        }
        kucoin_api_request("/api/v1/orders", "POST", sl_payload)
        
        # Programar Take Profit (Target 1)
        tp_payload = {
            "clientOid": str(int(time.time() * 1000) + 2),
            "side": contra_side,
            "symbol": symbol,
            "type": "limit",
            "price": float(formatear_precio(tp_price)),
            "size": cantidad_contratos,
            "positionSide": pos_side,
            "marginMode": modo_exitoso,
            "reduceOnly": True
        }
        kucoin_api_request("/api/v1/orders", "POST", tp_payload)
        
        enviar_telegram(f"💼 ¡Operación colocada con éxito en modo {modo_exitoso}! ⚡\n🛡️ SL en: {formatear_precio(sl_price)}\n🎯 TP Target 1 en: {formatear_precio(tp_price)}")

    except Exception as e:
        error_msg = f"❌ Error al intentar abrir orden en KuCoin: {str(e)}"
        print(error_msg)
        enviar_telegram(error_msg)

# ==========================================================
# 🔄 BUCLE PRINCIPAL (ALERTAS + CONTROL DE MARGEN)
# ==========================================================

# 1. Iniciamos el servidor web dummy en un hilo separado
hilo_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
hilo_web.start()

print("🚀 Bot iniciado correctamente.")

while True:
    for coin in MONEDAS_A_MONITOREAR:
        try:
            # Obtener precio directamente usando endpoints de Futuros (Sin Proxy)
            symbol_detalles, _ = obtener_detalles_contrato(coin)
            url_ticker = f"https://api-futures.kucoin.com/api/v1/ticker?symbol={symbol_detalles}"
            ticker_res = requests.get(url_ticker).json()
            
            if ticker_res.get("code") == "200000" and "data" in ticker_res:
                precio = float(ticker_res['data']['price'])
            else:
                raise Exception(f"No se pudo obtener el precio: {ticker_res.get('msg')}")
            
            HISTORIALES[coin].append(precio)
            if len(HISTORIALES[coin]) > 30: 
                HISTORIALES[coin].pop(0)
                
            rsi = calcular_rsi(HISTORIALES[coin])
            
            if rsi is None:
                print(f"Recolectando datos para {coin}... (Datos: {len(HISTORIALES[coin])}/15)")
            else:
                print(f"📈 {coin} -> Precio: {formatear_precio(precio)} | RSI: {rsi:.2f}")
                
                # Detectar Señales
                es_compra = (rsi < 30 and ESTADOS_ANTERIORES[coin] != "COMPRA")
                es_venta = (rsi > 70 and ESTADOS_ANTERIORES[coin] != "VENTA")
                
                if es_compra or es_venta:
                    direccion = "LONG" if es_compra else "SHORT"
                    msg_senal, stop_loss, take_profit = crear_senal(coin, direccion, precio)
                    
                    # Verificar posiciones actuales en KuCoin
                    posiciones_actuales = obtener_posiciones_abiertas()
                    
                    if posiciones_actuales < 2:
                        # Mandamos la alerta a Telegram y Ejecutamos la orden en KuCoin
                        enviar_telegram(msg_senal + f"\n\n🚀 HAY MARGEN ({posiciones_actuales}/2): Ejecutando en KuCoin...")
                        ejecutar_orden_futuros(coin, direccion, precio, stop_loss, take_profit)
                    else:
                        # Mandamos SOLAMENTE la alerta a Telegram porque tu dinero ya está ocupado
                        enviar_telegram(msg_senal + f"\n\n🚫 SIN MARGEN ({posiciones_actuales}/2 ocupado). Alerta informativa guardada.")
                        print(f"⚠️ Alerta enviada a Telegram. Sin margen para ejecutar en KuCoin ({posiciones_actuales}/2).")
                        
                    ESTADOS_ANTERIORES[coin] = "COMPRA" if es_compra else "VENTA"
                    
                elif 40 <= rsi <= 60:
                    ESTADOS_ANTERIORES[coin] = None
                    
        except Exception as e:
            print(f"Error procesando {coin}: {e}")
            
        time.sleep(1)
        
    print("--- Ciclo de análisis completado. Esperando para volver a escanear... ---")
    time.sleep(10)
