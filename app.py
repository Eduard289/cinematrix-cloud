
import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CineMatrix Privado", page_icon="🔐", layout="centered")

# --- SISTEMA DE SEGURIDAD (LOGIN) ---
# Define tu contraseña aquí o en los Secrets (mejor en secrets)
try:
    ACCESS_PASSWORD = st.secrets["APP_PASSWORD"]
except:
    ACCESS_PASSWORD = "admin" # Contraseña por defecto si no se configura

def check_password():
    """Retorna True si el usuario ha iniciado sesión correctamente."""
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
    st.stop() # Detiene la ejecución si no hay login

# --- GESTIÓN DE SECRETOS ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("⚠️ Falta configurar el RD_TOKEN en los Secrets.")
    st.stop()

# --- CONSTANTES ---
CINEMETA_URL = "https://v3-cinemeta.strem.io/catalog/movie/top/search={}.json"
TORRENTIO_URL = "https://torrentio.strem.fun/stream/movie/{}.json"
HEADERS = {"Authorization": f"Bearer {RD_TOKEN}"}
BASE_URL = "https://api.real-debrid.com/rest/1.0"

# --- FUNCIONES ---
def buscar_imdb(query):
    try:
        url = CINEMETA_URL.format(query)
        res = requests.get(url, timeout=5).json()
        if 'metas' in res: return res['metas']
    except: return []
    return []

def obtener_torrents(imdb_id):
    # Usamos proxies por seguridad
    proxies_list = ["https://api.allorigins.win/raw?url=", "https://corsproxy.io/?"]
    target_url = TORRENTIO_URL.format(imdb_id)
    
    for proxy in proxies_list:
        try:
            final_url = f"{proxy}{urllib.parse.quote(target_url)}"
            res = requests.get(final_url, timeout=5)
            if res.status_code == 200: 
                streams = res.json().get('streams', [])
                # Filtramos y limpiamos datos
                cleaned = []
                for s in streams:
                    title_parts = s['title'].split('\n')
                    calidad = "Desconocida"
                    seeders = "N/A"
                    for part in title_parts:
                        if "4k" in part.lower(): calidad = "🌟 4K UHD"
                        elif "1080p" in part.lower(): calidad = "📺 1080p"
                        elif "720p" in part.lower(): calidad = "📱 720p"
                        if "👤" in part: seeders = part # Torrentio suele poner seeders con este icono
                    
                    cleaned.append({
                        'title': title_parts[0],
                        'quality': calidad,
                        'seeds': seeders,
                        'infoHash': s['infoHash']
                    })
                return cleaned
        except: continue
    return []

def borrar_torrent(rd_id):
    requests.delete(f"{BASE_URL}/torrents/delete/{rd_id}", headers=HEADERS)

def procesar_rd(magnet):
    # 1. Añadir Magnet
    res = requests.post(f"{BASE_URL}/torrents/addMagnet", headers=HEADERS, data={"magnet": magnet})
    if res.status_code != 201: return None, None
    
    rd_id = res.json()['id']
    
    # 2. Seleccionar Archivo
    with st.spinner("☁️ Procesando en la nube (esto puede tardar unos segundos)..."):
        attempts = 0
        while attempts < 20:
            time.sleep(1)
            info = requests.get(f"{BASE_URL}/torrents/info/{rd_id}", headers=HEADERS).json()
            status = info['status']
            
            if status == 'waiting_files_selection':
                archivo_top = max(info['files'], key=lambda x: x['bytes'])
                requests.post(f"{BASE_URL}/torrents/selectFiles/{rd_id}", headers=HEADERS, data={"files": str(archivo_top['id'])})
            
            elif status == 'downloaded':
                link_fuente = info['links'][0]
                unrestrict = requests.post(f"{base_url}/unrestrict/link", headers=HEADERS, data={"link": link_fuente}).json()
                return unrestrict.get('download'), rd_id # Devolvemos link y ID para poder borrar
            
            elif status == 'error':
                return None, rd_id
            
            attempts += 1
    return None, rd_id

# --- INTERFAZ GRÁFICA ---
st.title("🍿 CineMatrix Privado")
st.markdown(f"Bienvenido. Sistema seguro activo.")

tab1, tab2 = st.tabs(["🔍 Buscador", "⚙️ Gestión Activa"])

with tab1:
    query = st.text_input("Buscar película:", placeholder="Escribe el título...")
    
    if query:
        resultados = buscar_imdb(query)
        if resultados:
            st.success(f"Encontradas {len(resultados)} películas.")
            sel_name = st.selectbox("Selecciona:", [m['name'] + f" ({m.get('releaseInfo','')})" for m in resultados])
            # Encontrar el objeto seleccionado
            seleccion = next(m for m in resultados if m['name'] in sel_name)
            
            if st.button("Buscar Enlaces"):
                streams = obtener_torrents(seleccion['imdb_id'])
                if streams:
                    st.write("### Resultados Disponibles")
                    for s in streams[:8]: # Top 8
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{s['title']}**")
                            st.caption(f"{s['quality']} | {s['seeds']}")
                        with col2:
                            if st.button("📥 Descargar", key=s['infoHash']):
                                magnet = f"magnet:?xt=urn:btih:{s['infoHash']}&dn={urllib.parse.quote(seleccion['name'])}"
                                link, rd_id = procesar_rd(magnet)
                                if link:
                                    st.success("¡Listo!")
                                    st.code(link)
                                    st.markdown(f"[Abrir Directamente]({link})")
                                    # Guardar en historial
                                    if 'historial' not in st.session_state: st.session_state.historial = []
                                    st.session_state.historial.append({'titulo': seleccion['name'], 'link': link, 'id': rd_id})
                                else:
                                    st.error("Error o timeout en Real-Debrid.")
                        st.divider()
                else:
                    st.warning("No se encontraron enlaces de calidad.")

with tab2:
    st.write("### 📜 Historial de Sesión y Limpieza")
    if 'historial' in st.session_state and st.session_state.historial:
        for idx, item in enumerate(st.session_state.historial):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(f"🎬 **{item['titulo']}**")
                st.code(item['link'])
            with c2:
                if st.button("🗑️ Borrar", key=f"del_{idx}"):
                    borrar_torrent(item['id'])
                    st.warning("Torrent eliminado de la nube RD.")
            st.divider()
    else:
        st.info("No hay descargas recientes en esta sesión.")
