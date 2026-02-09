import streamlit as st
import requests
import urllib.parse
import time

# ==========================================
#      CONFIGURACIÓN Y SECRETOS
# ==========================================

# Tu Token de Real-Debrid (Ya integrado)
RD_TOKEN = "3HXX4FQQMTNQ6XRUZA3XZL2ZN7IKZVZEVYK3HUC2LCE7WFJBFPYQ"

# Configuración de la página web
st.set_page_config(page_title="CineMatrix PC", page_icon="🍿", layout="centered")

# ==========================================
#      RED DE ESPEJOS (ANTI-BLOQUEO)
# ==========================================
# Esta lista permite que el script salte de un servidor a otro
# hasta encontrar uno que tu operador (Guuk) no haya bloqueado.
ESPEJOS = [
    "https://api.allorigins.win/raw?url=",      # Espejo 1 (Muy fiable)
    "https://corsproxy.io/?",                   # Espejo 2 (Rápido)
    "https://api.codetabs.com/v1/proxy?quest=", # Espejo 3
    "https://thingproxy.freeboard.io/fetch/",   # Espejo 4
    "https://api.cors.lol/?url=",               # Espejo 5
]

# URLs Base
CINEMETA_URL = "https://v3-cinemeta.strem.io/catalog/movie/top/search={}.json"
TORRENTIO_URL = "https://torrentio.strem.fun/stream/movie/{}.json"

# ==========================================
#           MOTORES DE BÚSQUEDA
# ==========================================

def buscar_cine(query):
    """Busca carátulas y nombres en Cinemeta"""
    try:
        url = CINEMETA_URL.format(query)
        # Intentamos conexión directa primero
        try:
            res = requests.get(url, timeout=3)
            data = res.json()
        except:
            # Si falla, usamos el primer espejo
            res = requests.get(ESPEJOS[0] + urllib.parse.quote(url), timeout=5)
            data = res.json()

        if 'metas' in data:
            return data['metas']
    except Exception as e:
        st.error(f"Error buscando peli: {e}")
    return []

def obtener_torrents_indestructible(imdb_id):
    """
    Busca enlaces en Torrentio usando la técnica 'Round Robin'
    para evadir bloqueos de operador.
    """
    target_url = TORRENTIO_URL.format(imdb_id)
    status_text = st.empty() # Espacio para mensajes de estado
    
    # 1. Intento Directo (Rápido)
    try:
        res = requests.get(target_url, timeout=2)
        if res.status_code == 200:
            return res.json().get('streams', [])
    except:
        pass # Fallo silencioso, activamos espejos

    # 2. Rotación de Espejos
    for i, espejo in enumerate(ESPEJOS):
        status_text.text(f"🔄 Probando ruta alternativa {i+1}...")
        try:
            # Codificamos la URL para que viaje segura
            final_url = f"{espejo}{urllib.parse.quote(target_url)}"
            res = requests.get(final_url, timeout=6)
            
            if res.status_code == 200:
                data = res.json()
                if 'streams' in data:
                    status_text.empty()
                    return data['streams']
        except:
            continue # Si falla, siguiente espejo
            
    status_text.error("❌ Todos los espejos fallaron. Revisa tu internet.")
    return []

# ==========================================
#           GESTOR REAL-DEBRID
# ==========================================

def procesar_en_nube(magnet):
    """Sube el magnet a RD y devuelve el link directo"""
    headers = {"Authorization": f"Bearer {RD_TOKEN}"}
    base_url = "https://api.real-debrid.com/rest/1.0"

    # 1. Subir Magnet
    res = requests.post(f"{base_url}/torrents/addMagnet", headers=headers, data={"magnet": magnet})
    if res.status_code != 201:
        st.error("Error al enviar a la nube (Token inválido o servicio caído).")
        return None
    
    rd_id = res.json()['id']
    
    # 2. Barra de progreso y selección de archivo
    barra = st.progress(0, text="☁️ Iniciando motor de la nube...")
    
    for i in range(15): # Intentos durante 15 segundos
        time.sleep(1)
        info = requests.get(f"{base_url}/torrents/info/{rd_id}", headers=headers).json()
        estado = info['status']
        
        if estado == 'waiting_files_selection':
            # Seleccionar el archivo más grande (la película)
            archivos = info['files']
            archivo_top = max(archivos, key=lambda x: x['bytes'])
            requests.post(f"{base_url}/torrents/selectFiles/{rd_id}", headers=headers, data={"files": str(archivo_top['id'])})
            barra.progress(50, text="📁 Archivo seleccionado. Descomprimiendo...")
        
        elif estado == 'downloaded':
            barra.progress(100, text="✨ ¡Completado!")
            # Obtener link final
            link_fuente = info['links'][0]
            unrestrict = requests.post(f"{base_url}/unrestrict/link", headers=headers, data={"link": link_fuente}).json()
            return unrestrict['download']
        
        elif estado == 'downloading':
            progreso_real = info.get('progress', 0)
            barra.progress(progreso_real, text=f"🚀 Descargando en servidores RD: {progreso_real}%")

    return None

# ==========================================
#           INTERFAZ GRÁFICA
# ==========================================

st.title("🍿 CineMatrix PC")
st.markdown("Tu estación de combate para streaming ilimitado.")

# --- PASO 1: BÚSQUEDA ---
col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("¿Qué quieres ver?", placeholder="Ej: Oppenheimer, Matrix...")
with col2:
    st.write("")
    st.write("")
    buscar_btn = st.button("🔍 Buscar")

if buscar_btn and query:
    resultados = buscar_cine(query)
    
    if resultados:
        # Guardamos resultados en sesión para no perderlos al recargar
        st.session_state['resultados'] = resultados
        st.session_state['streams'] = None # Limpiamos streams anteriores
    else:
        st.warning("No se encontraron resultados.")

# --- PASO 2: SELECCIÓN ---
if 'resultados' in st.session_state and st.session_state['resultados']:
    opciones = {f"{m['name']} ({m.get('releaseInfo', 'N/A')})": m for m in st.session_state['resultados']}
    seleccion_nombre = st.selectbox("Resultados encontrados:", list(opciones.keys()))
    
    if st.button("📡 Escanear Enlaces (Torrentio)"):
        seleccion = opciones[seleccion_nombre]
        with st.spinner("Saltando bloqueos de operador..."):
            streams = obtener_torrents_indestructible(seleccion['imdb_id'])
            st.session_state['streams'] = streams
            st.session_state['peli_actual'] = seleccion['name']

# --- PASO 3: GENERACIÓN ---
if 'streams' in st.session_state and st.session_state['streams']:
    st.divider()
    st.subheader(f"Enlaces para: {st.session_state['peli_actual']}")
    
    for s in st.session_state['streams'][:8]: # Mostramos los 8 mejores
        # Limpieza de título
        titulo = s['title'].split('\n')[0].replace('👤', '').strip()
        
        # Detector de Calidad Visual
        if "4k" in s['title'].lower(): icono = "🌟 4K UHD"
        elif "1080p" in s['title'].lower(): icono = "📺 1080p"
        else: icono = "📱 Calidad Std"
        
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.info(f"{icono} | {titulo}")
        with col_b:
            # Botón único por cada enlace
            if st.button("VER ▶️", key=s['infoHash']):
                magnet = f"magnet:?xt=urn:btih:{s['infoHash']}&dn={urllib.parse.quote(st.session_state['peli_actual'])}"
                
                link_final = procesar_en_nube(magnet)
                
                if link_final:
                    st.success("✅ ¡ENLACE LISTO!")
                    st.code(link_final)
                    st.link_button("Abrir en Navegador/VLC", link_final)
                else:
                    st.error("Error al procesar.")
