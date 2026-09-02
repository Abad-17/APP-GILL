import streamlit as st
import zipfile
import io
import pandas as pd
import base64
import fitz  # Lo importamos para extraer la imagen de portada en la UI
from datetime import datetime

# --- IMPORTACIÓN DE TUS MÓDULOS INTACTOS ---
from modulos.extraccion_pdf import extraer_metadatos
from modulos.exportador import preparar_dataframe_para_excel, estructurar_y_exportar_catalogacion

def obtener_imagen_base64(ruta_imagen):
    """Convierte una imagen local a base64 para inyectarla en CSS/HTML."""
    try:
        with open(ruta_imagen, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

def aplicar_estilos_institucionales():
    """Inyecta CSS avanzado para crear una interfaz idéntica a los portales de la UNAM."""
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 95% !important; 
    }
    .stApp { background-color: #F4F6F9; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
        border: 1px solid #E5E9F2 !important;
        padding: 15px;
        transition: transform 0.2s ease;
    }
    
    h1, h2, h3, h4, h5 { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    .titulo-tarjeta {
        color: #002B7A;
        font-weight: 700;
        border-bottom: 2px solid #F0F2F6;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }

    .stButton>button[kind="primary"] {
        background-color: #002B7A !important; 
        color: #ffffff !important;
        border-radius: 8px; 
        border: 2px solid #002B7A; 
        font-weight: bold; 
        width: 100%;
        padding: 0.6rem 1rem;
        font-size: 1.1rem;
        box-shadow: 0 4px 6px rgba(0,43,122,0.2);
        transition: all 0.3s ease;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #D59F0F !important; 
        border-color: #D59F0F !important; 
        color: #002B7A !important;
        box-shadow: 0 6px 12px rgba(213,159,15,0.3);
        transform: translateY(-2px);
    }

    .stProgress > div > div > div > div { background-color: #D59F0F !important; }

    [data-testid="stMetricValue"] { color: #002B7A !important; font-weight: 800 !important; }
    
    .unam-header-container {
        background-color: #002B7A;
        border-bottom: 6px solid #D59F0F;
        padding: 25px 40px;
        border-radius: 8px;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .unam-header-text h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: 0.5px;
    }
    .unam-header-text h2 {
        color: #D59F0F !important;
        margin: 5px 0 0 0;
        font-size: 1.4rem;
        font-weight: 400;
    }
    .unam-badge {
        background-color: rgba(255,255,255,0.1);
        padding: 8px 15px;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        font-size: 0.9rem;
        border: 1px solid rgba(255,255,255,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

def mostrar_header_unam():
    st.markdown("""
        <div class="unam-header-container">
            <div class="unam-header-text">
                <h1>Universidad Nacional Autónoma de México</h1>
                <h2>Biblioteca Nacional de México • Sistema de Catalogación con PLN</h2>
            </div>
            <div class="unam-badge">
                Versión 2.0 (PLN PAPIIT)
            </div>
        </div>
    """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="BNM | Catalogación con PLN", page_icon="🏛️", layout="wide")
    aplicar_estilos_institucionales()

    mostrar_header_unam()

    with st.sidebar:
        st.markdown("<h2 style='color:#002B7A; font-weight:bold;'>⚙️ Configuración</h2>", unsafe_allow_html=True)
        #st.info("**Motor Base:** PyMuPDF\n\n**Motor IA:** Qwen 2.5 (32B)\n\n**Red:** VPN UNAM", icon="🔒")
        st.info("**Motor Base:** PyMuPDF\n\n**Motor IA:** PLN\n\n**Red:** Local", icon="🔒")
        
        #st.markdown("### Conectividad")
        #st.error("⚠️ Es indispensable conectar el cliente FortiClient antes de iniciar el procesamiento.", icon="🚨")
        
        st.divider()
        st.markdown("### 🛠️ Control de Sesión")
        if st.button("🧹 Limpiar Memoria y Reiniciar"):
            st.session_state.clear()
            st.rerun()

        st.divider()
        st.markdown("### 📋 Instrucciones:")
        st.markdown("""
        1. Ingresa los archivos `.pdf` sueltos o en un archivo `.zip`.
        2. Presiona Iniciar Extracción.
        3. Verifica el monitor visual de procesamiento.
        4. Revisa la tabla de vista previa.
        5. Descarga la hoja de cálculo final (Excel).
        """)
        st.caption("© 2026 Universidad Nacional Autónoma de México")

    with st.container(border=True):
        st.markdown("<h3 class='titulo-tarjeta'>📥 Ingreso de Materiales Digitales</h3>", unsafe_allow_html=True)
        archivos_subidos = st.file_uploader("Arrastra tus documentos o haz clic para explorar", type=["pdf", "zip"], accept_multiple_files=True)

    if archivos_subidos:
        st.write("") 
        
        col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
        with col_b2:
            iniciar = st.button("🚀 Iniciar Extracción de Metadatos", type="primary")

        if iniciar:
            st.write("")
            with st.container(border=True):
                st.markdown("<h3 class='titulo-tarjeta'>⚙️ Monitor Visual de Procesamiento</h3>", unsafe_allow_html=True)
                
                archivos_a_procesar = [] 
                with st.spinner("Preparando y estructurando documentos..."):
                    for archivo in archivos_subidos:
                        if archivo.name.lower().endswith('.zip'):
                            zip_bytes = archivo.read()
                            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                                for file_name in z.namelist():
                                    if file_name.lower().endswith('.pdf') and not file_name.startswith('__MACOSX'):
                                        archivos_a_procesar.append((z.read(file_name), f"{archivo.name} -> {file_name.split('/')[-1]}"))
                        else:
                            archivos_a_procesar.append((archivo.read(), archivo.name))
                
                total = len(archivos_a_procesar)
                if total == 0:
                    st.error("⚠️ No se encontraron PDFs válidos.")
                    return

                c_met1, c_met2, c_met3 = st.columns(3)
                metrica_progreso = c_met1.empty()
                metrica_progreso.metric("Documentos a Procesar", f"0 / {total}")
                c_met2.metric("Motor Físico", "Activo", "Matemáticas/Regex")
                #c_met3.metric("Inteligencia Artificial", "Activo", "Qwen 32B Server")

                st.divider()

                # --- NUEVA INTERFAZ VISUAL EN DOS COLUMNAS ---
                col_visor, col_datos = st.columns([1, 2.5])
                
                with col_visor:
                    st.markdown("**Carátula Actual:**")
                    visor_portada = st.empty() # Espacio reservado para la imagen
                    
                with col_datos:
                    texto_ui = st.empty() 
                    barra_ui = st.progress(0.0)
                
                resultados = []
                
                for i, (pdf_bytes, nombre) in enumerate(archivos_a_procesar):
                    texto_ui.markdown(f"**📖 Analizando libro actual:** `{nombre}`\n\n*Extrayendo estructura y metadatos...*")
                    
                    # 1. Renderizar la imagen de la portada (PyMuPDF en UI)
                    try:
                        doc_temp = fitz.open(stream=pdf_bytes, filetype="pdf")
                        pix = doc_temp[0].get_pixmap(matrix=fitz.Matrix(0.8, 0.8)) # Escala reducida para UI
                        visor_portada.image(pix.tobytes(), caption="En análisis...", use_container_width=True)
                        doc_temp.close()
                    except Exception:
                        visor_portada.info("Sin previsualización de portada.")
                    
                    # 2. Extracción de datos real
                    meta = extraer_metadatos(pdf_bytes)
                    meta["archivo"] = nombre 
                    resultados.append(meta)
                    
                    metrica_progreso.metric("Documentos Procesados", f"{i+1} / {total}")
                    barra_ui.progress((i + 1) / total)

                visor_portada.empty() # Limpiamos la portada al final
                #texto_ui.success("✅ Extracción semántica y estructural completada.")
                texto_ui.success("✅ Extracción estructural y de metadatos completada.")

            #with st.spinner("Construyendo formato Alma..."):
            with st.spinner("Construyendo formato..."):
                df_crudo = pd.DataFrame(resultados)
                df_limpio = preparar_dataframe_para_excel(df_crudo)
                
                # Guardamos el DataFrame en el session state para la Vista Previa
                st.session_state.df_vista_previa = df_limpio
                
                # Pasamos una ruta vacía para que el exportador ignore el catálogo
                buffer_excel = estructurar_y_exportar_catalogacion(df_limpio, "")
                st.session_state.archivo_excel = buffer_excel

        # --- DESCARGA Y VISTA PREVIA ---
        if "archivo_excel" in st.session_state:
            st.write("")
            with st.container(border=True):
                st.markdown("<h3 class='titulo-tarjeta' style='color:#155724; border-bottom-color:#d4edda;'>🎉 ¡Lote Procesado Exitosamente!</h3>", unsafe_allow_html=True)
                
                # Renderizar la Vista Previa de la Tabla
                st.markdown("#### 📊 Vista Previa de Datos Extraídos")
                st.dataframe(st.session_state.df_vista_previa, use_container_width=True, height=250)
                
                #st.success("Los metadatos han sido extraídos, validados con IA y cruzados con el catálogo de autoridades. El archivo está listo para el sistema Alma.")
                st.success("Los metadatos han sido extraídos. El archivo está listo para descargar.")
                
                col_d1, col_d2, col_d3 = st.columns([1,2,1])
                with col_d2:
                    st.download_button(
                        label="📥 Descargar Hoja de Catalogación Oficial (Excel)",
                        data=st.session_state.archivo_excel.getvalue(),
                        file_name=f"Catalogacion_BNM_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()