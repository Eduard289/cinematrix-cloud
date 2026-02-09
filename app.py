import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CineMatrix Debug", page_icon="🐞")

# --- GESTIÓN DE SECRETOS ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("❌ ERROR CRÍTICO: No has configurado el 'RD_TOKEN' en los Secrets.")
    st.stop()

# --- CONSTANTES ---
CINEMETA_URL = "https://v3-cinemeta.strem.io/catalog/movie/top/search={}.json"
TORRENTIO_URL = "https://torrentio.strem.fun/stream/movie/{}.json"

# Lista ampliada de proxies para la nube
PROXIES = [
    "https://api.allorigins.win/raw?url=",
    "https://corsproxy.io/?",
    "https://api.codetabs.com/v1/proxy?quest=",
    "https://thingproxy.freeboard.io/fetch/",
]

# --- FUNCIONES DE LOG ---
def log(mensaje, tipo="info"):
    """Muestra mensajes solo si el modo detective está activo"""
    if st.session_state.get('debug_mode', False):
        if tipo == "info": st.info(f"ℹ️ {mensaje}")
        elif tipo == "error": st.error(f"❌ {mensaje}")
        elif tipo == "ok": st.success(f"✅ {mensaje}")
        elif tipo == "warn": st.warning(f"⚠️ {mensaje}")

# --- FUNCIONES PRINCIPALES ---
def buscar_imdb(query):
    log(f"Buscando en Cinemeta: {query}", "info")
    try:
        url = CINEMETA_URL.format(query)
        res = requests.get(url, timeout=5)
        log(f"Estado Cinemeta: {res.status_code}", "info")
        
        data = res.json()
        if 'metas' in data:
            log(f"Encontradas {len(data['metas'])} pelis", "ok")
            return data['metas']
    except Exception as e:
        log(f"Error conectando a Cinemeta: {e}", "error")
    return []

def obtener_torrents(imdb_id):
    target_url = TORRENTIO_URL.format(imdb_id)
    log(f"Objetivo: {target_url}", "info")
    
    # 1. Intento Directo
    log("Iniciando Intento 1: Conexión Directa...", "warn")
    try:
        res = requests.get(target_url, timeout=3)
        if res.status_code == 200:
            streams = res.json().get('streams', [])
            log(f"¡Directo funcionó! Streams: {len(streams)}", "ok")
            return streams
        else:
            log(f"Fallo directo. Código: {res.status_code}", "error")
    except Exception as e:
        log(f"Excepción directa: {e}", "error")
    
    # 2. Intento Proxies
    log("Iniciando Protocolo de Proxies...", "warn")
    for i, proxy in enumerate(PROXIES):
        try:
            final_url = f"{proxy}{urllib.parse.quote(target_url)}"
            log(f"Probando Espejo {i+1}: {proxy[:30]}...", "info")
            
            res = requests.get(final_url, timeout=8)
            
            if res.status_code == 200:
                # Verificamos que sea JSON válido
                try:
                    data = res.json()
                except:
                    log("El espejo devolvió texto, no JSON válido.", "error")
                    continue
                
                if 'streams' in data:
                    streams = data['streams']
                    log(f"¡ÉXITO con Espejo {i+1}! Streams encontrados: {len(streams)}", "ok")
                    return streams
                else:
                    log("JSON recibido pero sin 'streams'.", "warn")
            else:
                log(f"Espejo {i+1} falló. Código: {res.status_code}", "error")
                
        except Exception as e:
            log(f"Error crítico en Espejo {i+1}: {e}", "error")
            continue
            
    log("FATAL: Todos los intentos fallaron.", "error")
    return []

def procesar_rd(magnet):
    headers = {"Authorization": f"Bearer {RD_TOKEN}"}
    base_url = "https://api.real-debrid.com/rest/1.0"
    
    log("Enviando magnet a Real-Debrid...", "info")
    res = requests.post(f"{base_url}/torrents/addMagnet", headers=headers, data={"magnet": magnet})
    
    if res.status_code != 201:
        log(f"Error RD AddMagnet: {res.status_code} - {res.text}", "error")
        return None
        
    rd_id = res.json()['id']
    log(f"Magnet añadido. ID: {rd_id}", "ok")
    
    with st.spinner("Procesando en la nube..."):
        attempts = 0
        while attempts < 15:
            time.sleep(1)
            info = requests.get(f"{base_url}/torrents/info/{rd_id}", headers=headers).json()
            estado = info['status']
            
            if estado == 'waiting_files_selection':
                archivo_top = max(info['files'], key=lambda x: x['bytes'])
                requests.post(f"{base_url}/torrents/selectFiles/{rd_id}", headers=headers, data={"files": str(archivo_top['id'])})
                log("Archivo seleccionado.", "info")
            
            elif estado == 'downloaded':
                link_fuente = info['links'][0]
                unrestrict = requests.post(f"{base_url}/unrestrict/link", headers=headers, data={"link": link_fuente}).json()
                return unrestrict['download']
            
            attempts += 1
    return None

# --- INTERFAZ ---
st.title("🕵️ CineMatrix Debugger")
st.checkbox("Activar Modo Detective (Ver Logs)", key="debug_mode")

query = st.text_input("Película:")

if st.button("Buscar") and query:
    resultados = buscar_imdb(query)
    
    if resultados:
        opciones = {f"{m['name']} ({m.get('releaseInfo', 'N/A')})": m for m in resultados}
        seleccion_nombre = st.selectbox("Resultados:", list(opciones.keys()))
        
        if st.button("Escanear Enlaces"):
            seleccion = opciones[seleccion_nombre]
            streams = obtener_torrents(seleccion['imdb_id'])
            
            if streams:
                for s in streams[:5]:
                    titulo = s['title'].split('\n')[0]
                    if st.button(f"🎬 {titulo}", key=s['infoHash']):
                        magnet = f"magnet:?xt=urn:btih:{s['infoHash']}&dn={urllib.parse.quote(seleccion['name'])}"
                        link = procesar_rd(magnet)
                        if link:
                            st.success("¡Enlace generado!")
                            st.code(link)
                            st.link_button("Abrir Video", link)
            else:
                st.error("No se encontraron enlaces tras probar todos los métodos.")
