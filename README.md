# 🍿 CineMatrix Cloud | Private Streaming Hub

![Version](https://img.shields.io/badge/version-2.1.0-blue?style=flat-square)
![Status](https://img.shields.io/badge/status-production-success?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9%2B-FFD43B?style=flat-square&logo=python&logoColor=blue)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Real-Debrid](https://img.shields.io/badge/API-Real--Debrid-89CFF0?style=flat-square)

**CineMatrix Cloud** es una aplicación web *Serverless* diseñada para la gestión automatizada de contenido multimedia. Actúa como un middleware inteligente entre bases de datos de metadatos (Cinemeta), indexadores P2P (Torrentio) y servicios de descarga premium (Real-Debrid), permitiendo el streaming de alta velocidad sin dependencia de hardware local.

---

## 🔐 Características de Seguridad & Privacidad

Esta instancia ha sido fortificada para evitar bloqueos de IP y restricciones de cuenta:

* **Autenticación de Doble Capa:**
    * Gestión de API Token mediante variables de entorno encriptadas.
    * **Login Gate:** Sistema de control de acceso mediante contraseña de aplicación (`APP_PASSWORD`), impidiendo el uso público y protegiendo la cuenta Real-Debrid de baneos por *multi-IP usage*.
* **Enrutamiento Proxy:** Las peticiones a trackers públicos se realizan a través de proxies rotativos (`CORS-Anywhere`, `AllOrigins`) para ofuscar el origen de la petición de búsqueda.
* **Ephemeral Session State:** El historial de enlaces generados reside estrictamente en la memoria volátil de la sesión (RAM) y se destruye automáticamente al cerrar la pestaña o reiniciar el servidor.

## 🚀 Funcionalidades Técnicas

### 1. Motor de Búsqueda & Metadatos
* Integración con la API **v3 de Cinemeta**.
* Resolución de nombres difusa (Fuzzy matching) para encontrar títulos exactos y años de lanzamiento.

### 2. Indexación y Filtrado P2P
* Conexión asíncrona con trackers mediante **Torrentio Scraper**.
* **Algoritmo de Selección Inteligente:**
    * Detección y parseo de calidad de video (4K UHD, 1080p, HDR, Dolby Vision).
    * Análisis de salud del enjambre (Seeders/Leechers) para garantizar disponibilidad.
    * Extracción de Hash (InfoHash) para generación de Magnet Links.

### 3. Cloud Debrid Processing (CDP)
* **Conversión Instantánea:** Transforma enlaces Magnet en enlaces de descarga directa (HTTPS) utilizando la infraestructura de servidores de Real-Debrid.
* **Gestión de Archivos Remota:**
    * *Auto-Selection:* Algoritmo que selecciona automáticamente el archivo de video más grande dentro del contenedor torrent.
    * *Remote Delete:* Capacidad para eliminar torrents de la nube de Real-Debrid directamente desde la interfaz de usuario mediante llamadas a la API `DELETE /torrents/delete/{id}`.

---

## 🛠️ Stack Tecnológico

* **Frontend/Backend:** Python 3.11 + Streamlit Framework.
* **Peticiones HTTP:** Librería `requests` con manejo de Timeouts y reintentos.
* **Procesamiento de Datos:** JSON Parsing y manipulación de cadenas para limpieza de títulos.
* **Despliegue:** Streamlit Community Cloud (Containerized Environment).

---

## ⚙️ Instalación y Despliegue

### Requisitos Previos
1.  Cuenta Premium en [Real-Debrid](https://real-debrid.com).
2.  Cuenta en GitHub.
3.  Python 3.9 o superior (para ejecución local).

### Configuración de Secretos (Environment Variables)
Para que la aplicación funcione, es imperativo configurar el archivo `.streamlit/secrets.toml` (local) o los **Secrets** en el panel de control de Streamlit Cloud:

```toml
# Token privado de la API de Real-Debrid ([https://real-debrid.com/apitoken](https://real-debrid.com/apitoken))
RD_TOKEN = "TU_TOKEN_REAL_DEBRID_AQUI"

# Contraseña de acceso para proteger la interfaz web
APP_PASSWORD = "TU_CONTRASEÑA_SEGURA"
