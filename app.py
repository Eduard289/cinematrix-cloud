import streamlit as st
import requests
import urllib.parse
import time
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CineMatrix Privado", page_icon="🔐", layout="centered")

# --- SISTEMA DE SEGURIDAD (LOGIN) ---
try:
    ACCESS_PASSWORD = st.secrets["APP_PASSWORD"]
except:
    ACCESS_PASSWORD = "admin" 

def check_password():
    if 'password_correct' not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    
    st.markdown("### 🔐 Acceso Restringido")
    pwd = st.text_input("Introduce la contraseña de acceso:", type="password")
    if st.button("Entrar"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    return False

if not check_password():
    st.stop() 

# --- GESTIÓN DE SECRETOS ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("⚠️ Falta configurar el RD_TOKEN en los Secrets.")
    st.stop()

# --- CONSTANTES ---
CINEMETA_URL = "https://v3-cinemeta.strem.io/catalog/movie/top/search={}.json"
# Usamos dos proveedores por si uno falla
PROVIDERS = [
    {"name": "Torrentio", "url": "https://torrentio.strem.fun/stream/movie/{}.json"},
    {"name": "KnightCrawler", "url": "https://knightcrawler.elfhosted.com/stream/movie/{}.json"}
]

HEADERS_RD = {"Authorization": f"Bearer {RD_TOKEN}"}
BASE_URL_RD = "https://api.real-debrid.com/rest/1.0"
# Cabeceras para parecer un navegador real y evitar bloqueos
FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

# --- FUNCIONES ---
def buscar_imdb(query):
    try:
        url = CINEMETA_URL.format(query)
        res = requests.get(url, timeout=5).json()
        if 'metas' in res: return res['metas']
    except: return []
    return []

def obtener_torrents(imdb_id):
    links_encontrados = []
    
    # Barra de progreso para ver qué está haciendo
    progress_text = "Escaneando trackers..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, provider in enumerate(PROVIDERS):
        try:
            target_url = provider["url"].format(imdb_id)
            # Intentamos conexión directa con headers falsos
            res = requests.get(target_url, headers=FAKE_HEADERS, timeout=6)
            
            if res.status_code == 200:
                data = res.json()
                streams = data.get('streams', [])
                
                for s in streams:
                    title_raw = s.get('title', 'Sin título').lower()
                    name_raw = s.get('name', '').lower()
                    
                    # Detección de calidad más flexible
                    calidad = "❓ Desconocida"
                    if "4k" in title_raw or "2160p" in title_raw: calidad = "🌟 4K UHD"
                    elif "1080p" in title_raw: calidad = "📺 1080p"
                    elif "720p" in title_raw: calidad = "📱 720p"
                    elif "hdr" in title_raw: calidad = "🌈 HDR"
                    
                    # Detección de semillas (Seeders)
                    seeders = "N/A"
                    # Torrentio suele poner "👤 123" en el título
                    if "👤" in s.get('title', ''):
                        parts = s['title'].split('\n')
                        for p in parts:
                            if "👤" in p: seeders = p.strip()
                    
                    links_encontrados.append({
                        'provider': provider['name'],
                        'title': s.get('title', 'Link').split('\n')[0],
                        'quality': calidad,
                        'seeds': seeders,
                        'infoHash': s['infoHash']
                    })
            else:
                print(f"Error {res.status_code} en {provider['name']}")
                
        except Exception as e:
            print(f"Excepción en {provider['name']}: {e}")
        
        my_bar.progress((i + 1) * 50, text=f"Analizando {provider['name']}...")
        
    my_bar.empty()
    return links_encontrados

def procesar_rd(magnet):
    # 1. Añadir Magnet
    res = requests.post(f"{BASE_URL_RD}/torrents/addMagnet", headers=HEADERS_RD, data={"magnet": magnet})
    if res.status_code != 201: 
        st.error(f"Error API Real-Debrid: {res.status_code}")
        return None, None
    
    rd_id = res.json()['id']
    
    # 2. Seleccionar Archivo
    with st.spinner("☁️ Procesando en la nube (Real-Debrid)..."):
        attempts = 0
        while attempts < 20:
            time.sleep(1)
            try:
                info = requests.get(f"{BASE_URL_RD}/torrents/info/{rd_id}", headers=HEADERS_RD).json()
                status = info['status']
                
                if status == 'waiting_files_selection':
                    archivo_top = max(info['files'], key=lambda x: x['bytes'])
                    requests.post(f"{BASE_URL_RD}/torrents/selectFiles/{rd_id}", headers=HEADERS_RD, data={"files": str(archivo_top['id'])})
                
                elif status == 'downloaded':
                    link_fuente = info['links'][0]
                    unrestrict = requests.post(f"{BASE_URL_RD}/unrestrict/link", headers=HEADERS_RD, data={"link": link_fuente}).json()
                    return unrestrict.get('download'), rd_id
                
                elif status == 'magnet_error':
                    st.error("El magnet es inválido o está muerto.")
                    return None, rd_id
            except:
                pass
            attempts += 1
    return None, rd_id

def borrar_torrent(rd_id):
    if rd_id:
        requests.delete(f"{BASE_URL_RD}/torrents/delete/{rd_id}", headers=HEADERS_RD)

# --- INTERFAZ GRÁFICA ---
st.title("🍿 CineMatrix V3")
st.caption("Conexión: Torrentio + KnightCrawler")

tab1, tab2 = st.tabs(["🔍 Buscador Universal", "⚙️ Descargas Activas"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Película o Serie:", placeholder="Ej: Gladiator 2...")
    with col2:
        st.write("") # Espacio
        st.write("") 
        buscar_btn = st.button("🔎 Buscar")
    
    if query:
        resultados = buscar_imdb(query)
        if resultados:
            st.success(f"Encontrados {len(resultados)} títulos.")
            
            # Selector inteligente
            opciones = {f"{m['name']} ({m.get('releaseInfo', 'N/A')})": m for m in resultados}
            seleccion_nombre = st.selectbox("Elige el correcto:", list(opciones.keys()))
            seleccion = opciones[seleccion_nombre]
            
            if st.button("🚀 EXTRAER ENLACES"):
                streams = obtener_torrents(seleccion['imdb_id'])
                
                if streams:
                    st.divider()
                    st.subheader(f"Enlaces para: {seleccion['name']}")
                    
                    # Mostrar resultados en tarjetas
                    for s in streams[:10]: # Top 10
                        with st.container():
                            c1, c2, c3 = st.columns([4, 2, 2])
                            with c1:
                                st.write(f"**{s['quality']}** | {s['title']}")
                                st.caption(f"Fuente: {s['provider']}")
                            with c2:
                                st.info(f"{s['seeds']}")
                            with c3:
                                if st.button("📥 Bajar", key=s['infoHash']):
                                    magnet = f"magnet:?xt=urn:btih:{s['infoHash']}&dn={urllib.parse.quote(seleccion['name'])}"
                                    link, rd_id = procesar_rd(magnet)
                                    
                                    if link:
                                        st.balloons()
                                        st.success("¡Enlace Generado!")
                                        st.code(link)
                                        st.markdown(f"[👉 Click para abrir]({link})")
                                        # Guardar historial
                                        if 'historial' not in st.session_state: st.session_state.historial = []
                                        st.session_state.historial.append({
                                            'titulo': seleccion['name'], 
                                            'link': link, 
                                            'id': rd_id,
                                            'time': time.strftime("%H:%M")
                                        })
                                    else:
                                        st.error("Error: Timeout o Torrent sin semillas.")
                            st.divider()
                else:
                    st.warning("⚠️ No se encontraron enlaces en ningún proveedor. Intenta con una película más popular.")
        elif query and not resultados:
            st.error("No se encontró la película en Cinemeta.")

with tab2:
    if 'historial' in st.session_state and st.session_state.historial:
        st.write(f"Tienes {len(st.session_state.historial)} enlaces generados en esta sesión.")
        for idx, item in enumerate(reversed(st.session_state.historial)):
            with st.expander(f"🎬 {item['titulo']} ({item['time']})"):
                st.code(item['link'])
                if st.button("🗑️ Borrar de la nube", key=f"del_{idx}"):
                    borrar_torrent(item['id'])
                    st.toast("Archivo eliminado de Real-Debrid")
    else:
        st.info("Historial vacío.")
