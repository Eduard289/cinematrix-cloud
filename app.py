import streamlit as st
import requests
import urllib.parse
import time
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CineMatrix Debug", page_icon="🐞", layout="wide")

# --- SISTEMA DE LOGS ---
if 'logs' not in st.session_state:
    st.session_state.logs = []

def log(mensaje, tipo="info"):
    """Guarda mensajes en el log visible"""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {tipo.upper()}: {mensaje}")

# --- GESTIÓN DE SECRETOS ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
    ACCESS_PASSWORD = st.secrets["APP_PASSWORD"]
except:
    st.error("⚠️ Faltan RD_TOKEN o APP_PASSWORD en Secrets.")
    st.stop()

# --- LOGIN ---
def check_password():
    if st.session_state.get('password_correct', False):
        return True
    
    st.markdown("### 🔐 Acceso Seguro")
    pwd = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Incorrecto")
    return False

if not check_password():
    st.stop()

# --- CONSTANTES ---
PROVIDERS = [
    {"name": "Torrentio", "url": "https://torrentio.strem.fun/stream/movie/{}.json"},
    {"name": "KnightCrawler", "url": "https://knightcrawler.elfhosted.com/stream/movie/{}.json"},
    {"name": "YTS (Alternativo)", "url": "https://yts.mx/api/v2/movie_details.json?imdb_id={}"} 
]

# Proxies para saltar bloqueo de operadoras
PROXIES = [
    "", # Intento directo primero
    "https://api.allorigins.win/raw?url=",
    "https://corsproxy.io/?",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- LÓGICA DE BÚSQUEDA ---
def obtener_torrents(imdb_id):
    st.session_state.logs = [] # Limpiar logs antiguos
    log(f"Iniciando búsqueda para ID: {imdb_id}", "start")
    
    enlaces = []
    
    progress_bar = st.progress(0)
    
    for i, provider in enumerate(PROVIDERS):
        url_base = provider["url"].format(imdb_id)
        
        # Intentamos con cada Proxy disponible
        for proxy in PROXIES:
            try:
                # Construir URL final
                if proxy:
                    target_url = f"{proxy}{urllib.parse.quote(url_base)}"
                    log(f"Probando {provider['name']} vía Proxy...", "try")
                else:
                    target_url = url_base
                    log(f"Probando {provider['name']} Directo...", "try")

                res = requests.get(target_url, headers=HEADERS, timeout=5)
                
                if res.status_code == 200:
                    data = res.json()
                    
                    # Lógica especial para Torrentio/KnightCrawler
                    if 'streams' in data:
                        streams = data['streams']
                        log(f"✅ {provider['name']}: {len(streams)} enlaces encontrados.", "success")
                        
                        for s in streams:
                            calidad = "Desconocida"
                            if "4k" in s['title'].lower(): calidad = "🌟 4K"
                            elif "1080p" in s['title'].lower(): calidad = "📺 1080p"
                            
                            enlaces.append({
                                'title': s['title'].split('\n')[0],
                                'quality': calidad,
                                'hash': s['infoHash'],
                                'source': provider['name']
                            })
                        break # Si funciona este provider, dejamos de probar proxies para él
                    else:
                        log(f"⚠️ {provider['name']} respondió pero sin 'streams'.", "warning")
                else:
                    log(f"❌ {provider['name']} Error HTTP {res.status_code}", "error")

            except Exception as e:
                log(f"❌ Error conexión {provider['name']}: {str(e)}", "error")
        
        progress_bar.progress((i + 1) * 30)
        
    return enlaces

def procesar_rd(magnet):
    url = "https://api.real-debrid.com/rest/1.0"
    h = {"Authorization": f"Bearer {RD_TOKEN}"}
    
    # Añadir
    r = requests.post(f"{url}/torrents/addMagnet", headers=h, data={"magnet": magnet})
    if r.status_code != 201: return None
    id_torrent = r.json()['id']
    
    # Seleccionar
    r = requests.get(f"{url}/torrents/info/{id_torrent}", headers=h).json()
    if r['status'] == 'waiting_files_selection':
        f = max(r['files'], key=lambda x: x['bytes'])
        requests.post(f"{url}/torrents/selectFiles/{id_torrent}", headers=h, data={"files": str(f['id'])})
    
    # Esperar link
    import time
    for _ in range(10):
        time.sleep(1)
        r = requests.get(f"{url}/torrents/info/{id_torrent}", headers=h).json()
        if r['status'] == 'downloaded':
            link = requests.post(f"{url}/unrestrict/link", headers=h, data={"link": r['links'][0]}).json()['download']
            return link
    return None

# --- INTERFAZ ---
st.title("🐞 CineMatrix: Modo Diagnóstico")

col_izq, col_der = st.columns([2, 1])

with col_izq:
    query = st.text_input("Buscar película:")
    if st.button("Buscar y Depurar"):
        # 1. Buscar ID en Cinemeta
        log(f"Consultando Cinemeta para: {query}")
        meta_res = requests.get(f"https://v3-cinemeta.strem.io/catalog/movie/top/search={query}.json").json()
        
        if 'metas' in meta_res and len(meta_res['metas']) > 0:
            peli = meta_res['metas'][0] # Cogemos la primera automáticamente para el test
            st.success(f"Película detectada: {peli['name']} (ID: {peli['imdb_id']})")
            
            # 2. Buscar Enlaces
            resultados = obtener_torrents(peli['imdb_id'])
            
            if resultados:
                st.write("### ✅ Resultados Finales")
                for r in resultados[:5]:
                    if st.button(f"📥 {r['quality']} | {r['title']}", key=r['hash']):
                        magnet = f"magnet:?xt=urn:btih:{r['hash']}&dn=Movie"
                        link = procesar_rd(magnet)
                        if link: st.code(link)
            else:
                st.error("No se encontraron enlaces válidos tras probar todos los métodos.")
        else:
            st.error("Cinemeta no encontró la película.")

with col_der:
    st.write("### 📟 Log del Sistema")
    st.caption("Aquí verás qué falla exactamente")
    caja_logs = st.empty()
    
    # Renderizar logs
    texto_logs = ""
    for l in st.session_state.logs:
        color = "black"
        if "ERROR" in l: color = "red"
        elif "SUCCESS" in l: color = "green"
        elif "TRY" in l: color = "blue"
        texto_logs += f":{color}[{l}]  \n"
    
    caja_logs.markdown(texto_logs)
