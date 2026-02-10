import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CineMatrix Pro", page_icon="🍿", layout="centered")

# --- SEGURIDAD (LOGIN) ---
if 'password_correct' not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct:
        return True
    
    st.markdown("### 🔐 Acceso Privado")
    try:
        SECRETO = st.secrets["APP_PASSWORD"]
    except:
        st.error("⚠️ Falta configurar APP_PASSWORD en Secrets.")
        st.stop()
        
    pwd = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if pwd == SECRETO:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    return False

if not check_password():
    st.stop()

# --- GESTIÓN DE SECRETOS ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("⚠️ Falta el RD_TOKEN en Secrets.")
    st.stop()

# --- CONSTANTES ---
# ⚠️ AQUÍ ESTÁ LA MAGIA: Usamos "Mirrors" (Espejos) que no suelen estar bloqueados
PROVIDERS = [
    # Espejo 1: Torrentio ElfHosted (Suele funcionar siempre)
    {"name": "Torrentio (Mirror)", "url": "https://torrentio.elfhosted.com/stream/movie/{}.json"},
    # Espejo 2: KnightCrawler (Backup potente)
    {"name": "KnightCrawler", "url": "https://knightcrawler.elfhosted.com/stream/movie/{}.json"},
    # Espejo 3: Annatar (Otro motor rápido)
    {"name": "Annatar", "url": "https://annatar.elfhosted.com/stream/movie/{}.json"}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# --- FUNCIONES ---
def buscar_imdb(query):
    try:
        # Usamos Cinemeta para buscar
        url = f"https://v3-cinemeta.strem.io/catalog/movie/top/search={query}.json"
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        if 'metas' in res: return res['metas']
    except: return []
    return []

def obtener_torrents(imdb_id):
    links = []
    
    # Barra de progreso visual
    progreso = st.progress(0, text="Iniciando escaneo de espejos...")
    
    for i, provider in enumerate(PROVIDERS):
        try:
            target_url = provider["url"].format(imdb_id)
            # Hacemos la petición directa (confiando en los Mirrors + 1.1.1.1)
            res = requests.get(target_url, headers=HEADERS, timeout=6)
            
            if res.status_code == 200:
                data = res.json()
                if 'streams' in data:
                    streams = data['streams']
                    
                    for s in streams:
                        # Filtramos para limpiar el título
                        titulo_raw = s.get('title', 'Sin título').replace('\n', ' ')
                        
                        # Detectar Calidad
                        calidad = "📺 SD/HD"
                        if "4k" in titulo_raw.lower() or "2160p" in titulo_raw: calidad = "🌟 4K UHD"
                        elif "1080p" in titulo_raw: calidad = "FULL HD 1080p"
                        elif "720p" in titulo_raw: calidad = "HD 720p"
                        
                        # Detectar Seeds (Semillas)
                        seeders = "N/A"
                        if "👤" in titulo_raw:
                            parts = titulo_raw.split("👤")
                            if len(parts) > 1:
                                seeders = "👤 " + parts[1].split()[0]
                        
                        links.append({
                            'provider': provider['name'],
                            'title': titulo_raw[:60] + "...", # Recortamos títulos muy largos
                            'quality': calidad,
                            'seeds': seeders,
                            'hash': s['infoHash']
                        })
        except Exception as e:
            print(f"Error en {provider['name']}: {e}")
            
        progreso.progress((i + 1) * 33, text=f"Analizando {provider['name']}...")
        
    progreso.empty()
    return links

def procesar_rd(magnet):
    base_url = "https://api.real-debrid.com/rest/1.0"
    auth = {"Authorization": f"Bearer {RD_TOKEN}"}
    
    # 1. Añadir Magnet
    try:
        res = requests.post(f"{base_url}/torrents/addMagnet", headers=auth, data={"magnet": magnet})
        if res.status_code != 201: return None, "Error al añadir magnet"
        rd_id = res.json()['id']
        
        # 2. Seleccionar Archivo
        attempts = 0
        with st.spinner("⚡ Convirtiendo en enlace premium..."):
            while attempts < 15:
                time.sleep(1)
                info = requests.get(f"{base_url}/torrents/info/{rd_id}", headers=auth).json()
                status = info['status']
                
                if status == 'waiting_files_selection':
                    # Seleccionar el archivo más grande
                    archivo_top = max(info['files'], key=lambda x: x['bytes'])
                    requests.post(f"{base_url}/torrents/selectFiles/{rd_id}", headers=auth, data={"files": str(archivo_top['id'])})
                
                elif status == 'downloaded':
                    link_fuente = info['links'][0]
                    unrestrict = requests.post(f"{base_url}/unrestrict/link", headers=auth, data={"link": link_fuente}).json()
                    return unrestrict.get('download'), rd_id
                
                attempts += 1
    except:
        return None, "Excepción de conexión"
        
    return None, "Tiempo de espera agotado"

def borrar_torrent(rd_id):
    requests.delete(f"https://api.real-debrid.com/rest/1.0/torrents/delete/{rd_id}", 
                    headers={"Authorization": f"Bearer {RD_TOKEN}"})

# --- INTERFAZ GRÁFICA ---
st.title("🍿 CineMatrix: Mirrors Edition")
st.markdown("Acceso por ruta alternativa (ElfHosted).")

tab1, tab2 = st.tabs(["🔎 BUSCADOR", "📂 HISTORIAL"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Título de la película:", placeholder="Ej: Oppenheimer...")
    with col2:
        st.write("")
        st.write("")
        btn_buscar = st.button("Buscar 🚀")
        
    if query:
        resultados = buscar_imdb(query)
        if resultados:
            st.success(f"Encontradas {len(resultados)} coincidencias.")
            
            # Selector
            opciones = {f"{m['name']} ({m.get('releaseInfo', 'N/A')})": m for m in resultados}
            sel_nombre = st.selectbox("Selecciona la correcta:", list(opciones.keys()))
            seleccion = opciones[sel_nombre]
            
            if st.button(f"Ver Enlaces de '{seleccion['name']}'"):
                enlaces = obtener_torrents(seleccion['imdb_id'])
                
                if enlaces:
                    st.divider()
                    for link in enlaces[:10]: # Top 10 mejores
                        c1, c2, c3 = st.columns([5, 2, 2])
                        with c1:
                            st.write(f"**{link['quality']}**")
                            st.caption(f"{link['title']}")
                        with c2:
                            st.info(f"{link['seeds']}")
                        with c3:
                            if st.button("📥 Bajar", key=link['hash']):
                                magnet = f"magnet:?xt=urn:btih:{link['hash']}&dn=Movie"
                                url_final, rd_id = procesar_rd(magnet)
                                
                                if url_final:
                                    st.balloons()
                                    st.success("¡Enlace Premium Generado!")
                                    st.code(url_final)
                                    st.markdown(f"[👉 Abrir en Navegador]({url_final})")
                                    
                                    # Guardar
                                    if 'historial' not in st.session_state: st.session_state.historial = []
                                    st.session_state.historial.append({
                                        'titulo': seleccion['name'],
                                        'url': url_final,
                                        'id': rd_id
                                    })
                                else:
                                    st.error("Error al generar enlace.")
                        st.divider()
                else:
                    st.warning("No se encontraron enlaces en los espejos. Intenta otra película.")

with tab2:
    if 'historial' in st.session_state and st.session_state.historial:
        st.write("### 🕒 Descargas de esta sesión")
        for item in reversed(st.session_state.historial):
            with st.expander(f"🎬 {item['titulo']}"):
                st.code(item['url'])
                if st.button("🗑️ Borrar de Real-Debrid", key=f"del_{item['id']}"):
                    borrar_torrent(item['id'])
                    st.toast("Archivo eliminado de la nube.")
    else:
        st.info("No has descargado nada aún.")
