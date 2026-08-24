# Extractor PLN - Sistema de Catalogación Automatizada

Herramienta de extracción de metadatos estructurales y semánticos diseñada para la automatización de flujos de catalogación (compatible con las reglas de catalogación MARC 21) en la **Biblioteca Nacional de México**. Desarrollado como parte de las asignaciones de servicio social y apoyado por el programa **PAPIIT** en la Facultad de Ingeniería de la UNAM.

## 📁 Estructura del Directorio
Para que el entorno funcione correctamente, el proyecto debe mantener la siguiente estructura estricta. Nota que los archivos de lógica deben estar dentro de un paquete llamado `modulos`:

```text
extractor-pln/
│
├── app.py                  # Interfaz gráfica principal (Streamlit)
├── run_app.py              # Script de ejecución para consola/PyInstaller
├── modulos/                # Paquete con la lógica principal
│   ├── __init__.py         # Archivo vacío necesario para reconocer el paquete
│   ├── exportador.py       # Lógica de estructuración y exportación a Excel
│   ├── extraccion_pdf.py   # Lógica de procesamiento PyMuPDF y NER con spaCy
│   └── motor_ia.py         # Interfaz de conexión con el LLM Qwen2.5-32B
│
├── modelo_base_es/         # [Carpeta a descargar] Modelo base de spaCy
└── modelo_finetuned_ner_lg/# [Carpeta a descargar] Modelo afinado (NER)
```

## 🛠️ Requisitos e Instalación

1.  **Clonar el repositorio y crear un entorno virtual** (se recomienda Python 3.10+):
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    ```

2.  **Instalar las dependencias requeridas**:
    ```bash
    pip install pandas spacy openpyxl xlsxwriter PyMuPDF unidecode streamlit openai
    ```

## 🧠 Descarga de Modelos de Procesamiento (spaCy)
Debido a restricciones de tamaño en GitHub, los modelos de lenguaje natural necesarios para la extracción precisa de lugares de publicación y editoriales están alojados de forma externa en Google Drive.

**Instrucciones:**
1.  Descarga los modelos desde el siguiente enlace:
    👉 **https://drive.google.com/drive/folders/1hcFK4HbWDN6b16pd79-Mb4LD4_Efpr6D?usp=sharing**
2.  Descomprime los archivos descargados.
3.  Coloca las carpetas resultantes llamadas `modelo_base_es` y `modelo_finetuned_ner_lg` directamente en la raíz del proyecto (al mismo nivel que `app.py`).

## ⚙️ Configuración del Motor IA (Qwen2.5-32B)
El extractor puede apoyarse en un modelo local de **Qwen2.5-32B** para inferir temas y corregir títulos desordenados.

Por defecto, el archivo `modulos/motor_ia.py` está configurado para conectarse al servidor GIL de la UNAM (`http://132.247.131.251:8000/v1`). 
*   **Si usas el servidor institucional:** Asegúrate de tener activa tu conexión VPN mediante FortiClient antes de ejecutar la aplicación.
*   **Si ejecutas el modelo localmente:** Modifica la variable `base_url` en `modulos/motor_ia.py` para que apunte a tu instancia local (por ejemplo, `http://localhost:8000/v1`).

*(Nota: Para activar estas funciones en la interfaz gráfica, asegúrate de descomentar las líneas correspondientes a `motor_ia` tanto en `extraccion_pdf.py` como en `app.py`).*

## 🚀 Ejecución
Para arrancar la interfaz gráfica, ejecuta el siguiente comando en tu terminal:

```bash
streamlit run app.py
```
O de forma alternativa:
```bash
python run_app.py
```
