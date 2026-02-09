import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="CineMatrix Web", page_icon="🍿", layout="centered")

# --- GESTIÓN DE SECRETOS ---
# Esto buscará el token en la configuración segura de Streamlit Cloud
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("⚠️ No se ha configurado el Token de Real-Debrid en los 'Secrets' de la app.")
    st.info("Ve a Manage App -> Settings -> Secrets y añade: RD_TOKEN = 'tu_token_aqui'")
    st.stop()

# --- CONSTANTES ---
CINEMETA_URL = "https://v3-cinemeta.strem.io/catalog/movie/top/search={}.json"
TORRENTIO_URL = "https://torrentio.strem.fun/stream/movie/{}.json"
PROXIES = [
    "https://api.allorigins.win/raw?url=",
    "https://corsproxy.io/?",
]

# --- FUNCIONES ---
def buscar_imdb(query):
    try:
        url = CINEMETA_URL.format(query)
        res = requests.get(url, timeout=5).json()
        if 'metas' in res: return res['metas']
    except: return []
    return []

def obtener_torrents(imdb_id):
    target_url = TORRENTIO_URL.format(imdb_id)
    # Intento Directo
    try:
        res = requests.get(target_url, timeout=3)
        if res.status_code == 200: return res.json().get('streams', [])
    except: pass
    
    # Intento Proxies (por si el servidor bloquea)
    for proxy in PROXIES:
        try:
            final_url = f"{proxy}{urllib.parse.quote(target_url)}"
            res = requests.get(final_url, timeout=5)
            if res.status_code == 200: return res.json().get('streams', [])
        except: continue
    return []

def procesar_rd(magnet):
    headers = {"Authorization": f"Bearer {RD_TOKEN}"}
    base_url = "https://api.real-debrid.com/rest/1.0"
    
    # 1. Añadir Magnet a Real-Debrid
    data = {"magnet": magnet}
    res = requests.post(f"{base_url}/torrents/addMagnet", headers=headers, data=data)
    
    if res.status_code != 201:
        st.error(f"Error al enviar magnet: {res.status_code}")
        return None
        
    rd_id = res.json()['id']
    
    # 2. Seleccionar Archivo (Esperamos a que RD procese el torrent)
    with st.spinner("☁️ La nube está procesando el torrent..."):
        attempts = 0
        while attempts < 15: # 15 segundos máximo
            time.sleep(1)
            info = requests.get(f"{base_url}/torrents/info/{rd_id}", headers=headers).json()
            status = info['status']
            
            if status == 'waiting_files_selection':
                # Seleccionamos el archivo más grande (generalmente la película)
                archivo_top = max(info['files'], key=lambda x: x['bytes'])
                requests.post(f"{base_url}/torrents/selectFiles/{rd_id}", headers=headers, data={"files": str(archivo_top['id'])})
            
            elif status == 'downloaded':
                # Ya está listo, generamos el enlace directo
                link_fuente = info['links'][0]
                unrestrict = requests.post(f"{base_url}/unrestrict/link", headers=headers, data={"link": link_fuente}).json()
                return unrestrict['download']
            
            attempts += 1
    return None

# --- INTERFAZ GRÁFICA ---
st.title("🍿 CineMatrix Cloud")
st.markdown("Tu buscador privado de streaming con Real-Debrid.")

# Pestañas
tab1, tab2 = st.tabs(["🔍 Buscar", "📜 Historial (Sesión)"])

with tab1:
    query = st.text_input("¿Qué quieres ver hoy?", placeholder="Ej: Matrix, Avatar...")
    
    if query:
        resultados = buscar_imdb(query)
        if resultados:
            st.success(f"Encontradas {len(resultados)} coincidencias.")
            
            # Selector de película
            opciones = {f"{m['name']} ({m.get('releaseInfo', 'N/A')})": m for m in resultados}
            seleccion_nombre = st.selectbox("Elige la película:", list(opciones.keys()))
            seleccion = opciones[seleccion_nombre]
            
            if st.button("Buscar Enlaces"):
                with st.spinner("Escaneando trackers..."):
                    streams = obtener_torrents(seleccion['imdb_id'])
                
                if streams:
                    st.markdown("### 📺 Calidades Disponibles")
                    # Mostramos solo los primeros 5 resultados para no saturar
                    for s in streams[:5]:
                        titulo = s['title'].split('\n')[0]
                        # Usamos el hash como key única para el botón
                        if st.button(f"🎬 {titulo}", key=s.get('infoHash', titulo)):
                            # Construcción correcta del magnet
                            info_hash = s['infoHash']
                            magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={urllib.parse.quote(seleccion['name'])}"
                            
                            link_final = procesar_rd(magnet_link)
                            
                            if link_final:
                                st.balloons()
                                st.success("¡Enlace generado!")
                                st.code(link_final)
                                st.markdown(f"[👉 Abrir / Descargar]({link_final})")
                                
                                # Guardar en historial de sesión
                                if 'historial' not in st.session_state:
                                    st.session_state.historial = []
                                st.session_state.historial.append({'titulo': seleccion['name'], 'link': link_final})
                            else:
                                st.error("No se pudo generar el enlace. Puede que el torrent tenga pocos seeds.")
                else:
                    st.warning("No se encontraron torrents activos para esta película.")

with tab2:
    if 'historial' in st.session_state and st.session_state.historial:
        st.write("Enlaces generados en esta sesión:")
        for item in st.session_state.historial:
            st.markdown(f"**{item['titulo']}**")
            st.code(item['link'])
            st.divider()
    else:
        st.info("El historial está vacío.")
