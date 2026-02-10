import streamlit as st
import requests
import urllib.parse
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CineMatrix Diagnóstico", page_icon="🚑", layout="wide")

# --- LOGIN ---
def check_password():
    if st.session_state.get('password_correct', False): return True
    pwd = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
    return False

if not check_password(): st.stop()

# --- LOGGING ---
if 'logs' not in st.session_state: st.session_state.logs = []

def log(mensaje, estado="INFO"):
    t = time.strftime("%H:%M:%S")
    icono = "🔹"
    if estado == "SUCCESS": icono = "✅"
    elif estado == "ERROR": icono = "❌"
    elif estado == "WARN": icono = "⚠️"
    st.session_state.logs.append(f"{t} {icono} {mensaje}")

# --- PROVEEDORES Y RUTAS ---
# Probaremos 3 vías para cada proveedor
PROVIDERS = [
    {"name": "Torrentio Original", "url": "https://torrentio.strem.fun/stream/movie/{}.json"},
    {"name": "Torrentio Mirror (Elf)", "url": "https://torrentio.elfhosted.com/stream/movie/{}.json"},
    {"name": "KnightCrawler", "url": "https://knightcrawler.elfhosted.com/stream/movie/{}.json"},
]

PROXIES = [
    {"name": "Directo (Sin Proxy)", "p": ""},
    {"name": "Proxy AllOrigins", "p": "https://api.allorigins.win/raw?url="},
    {"name": "Proxy CorsProxy", "p": "https://corsproxy.io/?"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- LÓGICA DE TEST ---
def test_connection(imdb_id):
    st.session_state.logs = [] # Limpiar
    log(f"Iniciando diagnóstico para ID: {imdb_id}")
    
    enlaces_validos = []
    
    # Barra de progreso
    bar = st.progress(0)
    total_steps = len(PROVIDERS) * len(PROXIES)
    step = 0
    
    for prov in PROVIDERS:
        for proxy in PROXIES:
            step += 1
            bar.progress(int((step / total_steps) * 100))
            
            target_url = prov['url'].format(imdb_id)
            if proxy['p']:
                final_url = f"{proxy['p']}{urllib.parse.quote(target_url)}"
            else:
                final_url = target_url
                
            try:
                log(f"Probando {prov['name']} vía {proxy['name']}...", "INFO")
                start_time = time.time()
                res = requests.get(final_url, headers=HEADERS, timeout=5)
                elapsed = round(time.time() - start_time, 2)
                
                if res.status_code == 200:
                    try:
                        data = res.json()
                        if 'streams' in data and len(data['streams']) > 0:
                            num = len(data['streams'])
                            log(f"¡ÉXITO! {prov['name']} ({proxy['name']}) -> {num} enlaces en {elapsed}s", "SUCCESS")
                            
                            # Guardamos uno de ejemplo
                            for s in data['streams'][:3]:
                                enlaces_validos.append({
                                    'title': s.get('title', 'Sin titulo').split('\n')[0],
                                    'hash': s['infoHash'],
                                    'source': f"{prov['name']} via {proxy['name']}"
                                })
                            # Si encontramos algo, podríamos parar, pero en diagnóstico seguimos
                        else:
                            log(f"Respuesta vacía (0 streams) de {prov['name']}", "WARN")
                    except:
                        log(f"Error JSON en {prov['name']}. Posible bloqueo HTML.", "ERROR")
                else:
                    log(f"Error HTTP {res.status_code} en {prov['name']}", "ERROR")
            
            except Exception as e:
                log(f"Fallo conexión: {str(e)[:50]}...", "ERROR")
                
    bar.empty()
    return enlaces_validos

# --- INTERFAZ ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🔍 Prueba de Conexión")
    query = st.text_input("Pelicula:", value="Gladiator")
    if st.button("Ejecutar Diagnóstico"):
        # Buscar ID
        try:
            meta = requests.get(f"https://v3-cinemeta.strem.io/catalog/movie/top/search={query}.json").json()
            if meta['metas']:
                movie = meta['metas'][0]
                st.info(f"Probando con: {movie['name']} ({movie['releaseInfo']})")
                res = test_connection(movie['imdb_id'])
                
                if res:
                    st.success("✅ Se encontraron rutas válidas.")
                    st.write("### Enlaces extraídos:")
                    for r in res:
                        st.code(f"{r['source']}\n{r['title']}")
                else:
                    st.error("❌ Ninguna ruta funcionó.")
            else:
                st.error("Película no encontrada en Cinemeta.")
        except Exception as e:
            st.error(f"Error crítico en Cinemeta: {e}")

with col2:
    st.subheader("📟 Log en Tiempo Real")
    log_container = st.container(height=500)
    for line in st.session_state.logs:
        if "✅" in line:
            log_container.success(line)
        elif "❌" in line:
            log_container.error(line)
        else:
            log_container.text(line)info("No has descargado nada aún.")
