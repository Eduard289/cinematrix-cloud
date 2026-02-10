import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CineMatrix Final", page_icon="🎬", layout="centered")

# --- LOGIN (Tu seguridad) ---
if 'password_correct' not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    st.markdown("### 🔐 Acceso CineMatrix")
    try:
        if st.text_input("Contraseña:", type="password") == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
    except:
        st.error("⚠️ Configura APP_PASSWORD en Secrets")
        st.stop()
    return False

if not check_password(): st.stop()

# --- GESTIÓN DE TOKEN ---
try:
    RD_TOKEN = st.secrets["RD_TOKEN"]
except:
    st.error("Falta RD_TOKEN")
    st.stop()

# --- CONSTANTES ---
# Usamos APIs que NO suelen bloquear a servidores Cloud
PROVIDERS = [
    # 1. YTS: La mejor para películas (API Pública y abierta)
    {"name": "YTS.mx (Oficial)", "type": "yts", "url": "https://yts.mx/api/v2/movie_details.json?imdb_id={}"},
    # 2. Annatar: Un clon de Torrentio hospedado en ElfHosted (Suele ser permisivo)
    {"name": "Annatar (Elf)", "type": "stremio", "url": "https://annatar.elfhosted.com/stream/movie/{}.json"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# --- FUNCIONES ---
def buscar_imdb(query):
    try:
        url = f"https://v3-cinemeta.strem.io/catalog/movie/top/search={query}.json"
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        if 'metas' in res: return res['metas']
    except: return []
    return []

def obtener_enlaces(imdb_id):
    links = []
    
    # Barra de carga
    progreso = st.progress(0, text="Buscando en YTS y Annatar...")
    
    for i, prov in enumerate(PROVIDERS):
        try:
            target = prov['url'].format(imdb_id)
            res = requests.get(target, headers=HEADERS, timeout=8)
            
            if res.status_code == 200:
                data = res.json()
                
                # --- PARSER PARA YTS ---
                if prov['type'] == 'yts':
                    if 'data' in data and 'movie' in data['data'] and 'torrents' in data['data']['movie']:
                        movie_title = data['data']['movie']['title']
                        for t in data['data']['movie']['torrents']:
                            calidad = f"🌟 {t['quality']} ({t['type']})"
                            seeds = f"👤 {t['seeds']}"
                            # Construir magnet manualmente para YTS
                            magnet = f"magnet:?xt=urn:btih:{t['hash']}&dn={urllib.parse.quote(movie_title)}"
                            
                            links.append({
                                'source': "🟢 YTS.mx",
                                'title': f"{movie_title} [{t['quality']}]",
                                'quality': calidad,
                                'seeds': seeds,
                                'magnet': magnet
                            })

                # --- PARSER PARA STREMIO (Annatar) ---
                elif prov['type'] == 'stremio':
                    if 'streams' in data:
                        for s in data['streams']:
                            title_raw = s.get('title', 'Link').split('\n')[0]
                            calidad = "📺 HD"
                            if "4k" in title_raw.lower(): calidad = "🌟 4K"
                            elif "1080p" in title_raw.lower(): calidad = "📺 1080p"
                            
                            links.append({
                                'source': "🔵 Annatar",
                                'title': title_raw,
                                'quality': calidad,
                                'seeds': "N/A",
                                'magnet': f"magnet:?xt=urn:btih:{s['infoHash']}&dn=Movie"
                            })
                            
        except Exception as e:
            print(f"Error en {prov['name']}: {e}")
            
        progreso.progress((i + 1) * 50)
        
    progreso.empty()
    return links

def procesar_rd(magnet):
    # API Real-Debrid
    url = "https://api.real-debrid.com/rest/1.0"
    auth = {"Authorization": f"Bearer {RD_TOKEN}"}
    
    try:
        # 1. Añadir
        add = requests.post(f"{url}/torrents/addMagnet", headers=auth, data={"magnet": magnet})
        if add.status_code != 201: return None
        rd_id = add.json()['id']
        
        # 2. Seleccionar archivo
        with st.spinner("☁️ Desencriptando en Real-Debrid..."):
            attempts = 0
            while attempts < 10:
                time.sleep(1)
                info = requests.get(f"{url}/torrents/info/{rd_id}", headers=auth).json()
                if info['status'] == 'waiting_files_selection':
                    f = max(info['files'], key=lambda x: x['bytes'])
                    requests.post(f"{url}/torrents/selectFiles/{rd_id}", headers=auth, data={"files": str(f['id'])})
                elif info['status'] == 'downloaded':
                    link = requests.post(f"{url}/unrestrict/link", headers=auth, data={"link": info['links'][0]}).json()
                    return link.get('download')
                elif info['status'] == 'error':
                    return None
                attempts += 1
    except:
        return None
    return None

# --- INTERFAZ ---
st.title("🍿 CineMatrix Final")
st.caption("Motores: YTS + Annatar")

tab1, tab2 = st.tabs(["BUSCADOR", "AYUDA"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("Película:", placeholder="Ej: Gladiator")
    with col2:
        st.write("")
        st.write("")
        btn = st.button("Buscar")

    if q:
        res = buscar_imdb(q)
        if res:
            st.success(f"Encontradas: {len(res)}")
            sel_txt = st.selectbox("Elige:", [f"{r['name']} ({r.get('releaseInfo','?')})" for r in res])
            sel = next(r for r in res if f"{r['name']} ({r.get('releaseInfo','?')})" == sel_txt)
            
            if st.button(f"Ver Enlaces de {sel['name']}"):
                resultados = obtener_enlaces(sel['imdb_id'])
                
                if resultados:
                    st.divider()
                    for item in resultados[:8]:
                        with st.container():
                            c1, c2, c3 = st.columns([4, 2, 2])
                            with c1:
                                st.write(f"**{item['quality']}**")
                                st.caption(f"{item['title']}")
                            with c2:
                                st.write(item['source'])
                                st.caption(item['seeds'])
                            with c3:
                                if st.button("📥 Bajar", key=item['title'][:10]+item['source']):
                                    link_final = procesar_rd(item['magnet'])
                                    if link_final:
                                        st.balloons()
                                        st.success("¡Listo!")
                                        st.code(link_final)
                                        st.markdown(f"[👉 Abrir Link]({link_final})")
                                    else:
                                        st.error("Error al procesar en RD")
                        st.divider()
                else:
                    st.error("No se encontraron enlaces en YTS ni Annatar. Intenta otra peli.")
        else:
            st.warning("No encontrada en Cinemeta.")

with tab2:
    st.info("Si YTS falla, prueba con pelis muy famosas (Avatar, Matrix, etc).")
