import flet as ft
import zipfile
import io
import asyncio
import base64
import pandas as pd
import pymupdf  # PyMuPDF (antes 'fitz')
from datetime import datetime

# --- IMPORTACIÓN DE MÓDULOS DEL PROYECTO PAPIIT ---
from modulos.extraccion_pdf import extraer_metadatos
from modulos.exportador import preparar_dataframe_para_excel

# --- PALETA INSTITUCIONAL UNAM ---
AZUL_UNAM = "#002B7A"
DORADO_UNAM = "#D59F0F"
FONDO = "#F4F6F9"
BORDE = "#E5E9F2"

# Píxel transparente de 1x1 codificado en Data URI para inicializar imágenes en Flet 0.86+ sin errores
PIXEL_TRANSPARENTE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def main(page: ft.Page):
    page.title = "BNM | Catalogación con PLN"
    page.bgcolor = FONDO
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(font_family="Segoe UI")
    page.window_min_width = 900
    page.window_min_height = 650

    # ==========================================
    # ESTADO GLOBAL DE LA APLICACIÓN
    # ==========================================
    state = {
        "archivos_pendientes": [],
        "archivos_procesados": [], 
        "datos_editables": [],     
        "columnas": [],
        "modo_edicion": False,
        "csv_bytes": None,
        "pdf_doc": None,           
        "pdf_pag": 0,              
    }

    # ==========================================
    # APPBAR
    # ==========================================
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.ACCOUNT_BALANCE, color=DORADO_UNAM, size=30),
        leading_width=60,
        title=ft.Column(
            [
                ft.Text("Universidad Nacional Autónoma de México", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Biblioteca Nacional de México • Sistema de Catalogación con PLN", size=12, color=DORADO_UNAM),
            ],
            spacing=0,
        ),
        bgcolor=AZUL_UNAM,
        center_title=False,
        actions=[
            ft.Container(
                content=ft.Text("Versión 2.0 (PLN PAPIIT)", color="white", weight=ft.FontWeight.BOLD, size=11),
                bgcolor="#ffffff1a",
                border=ft.Border.all(1, "#ffffff33"),
                border_radius=15,
                padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                margin=ft.Margin.only(right=20),
            )
        ],
    )

    # ==========================================
    # COMPONENTES VISUALES COMPARTIDOS
    # ==========================================
    texto_archivos = ft.Text("No hay documentos en la bandeja.", size=14, color="grey", text_align=ft.TextAlign.CENTER)
    indicador_progreso = ft.ProgressBar(value=0, color=DORADO_UNAM, bgcolor=BORDE, height=8)
    texto_progreso = ft.Text("Preparando entorno...", size=16, weight=ft.FontWeight.BOLD, color=AZUL_UNAM)
    consola_log = ft.ListView(expand=True, spacing=5, auto_scroll=True)
    tabla_resultados = ft.DataTable(columns=[], rows=[], border=ft.Border.all(1, BORDE), heading_row_color="#f0f2f6")

    # Se inicializan con el string Data URI directamente en src
    imagen_portada = ft.Image(src=PIXEL_TRANSPARENTE, width=250, height=350, fit=ft.BoxFit.CONTAIN, border_radius=8)

    # ==========================================
    # VISOR DE DOCUMENTOS DIGITALES (PDF INTERACTIVO)
    # ==========================================
    visor_img = ft.Image(src=PIXEL_TRANSPARENTE, fit=ft.BoxFit.CONTAIN)
    
    visor_interactivo = ft.InteractiveViewer(
        content=visor_img,
        max_scale=5.0, 
        min_scale=0.5,
        expand=True
    )
    
    visor_txt_pag = ft.Text("1 / 1", weight=ft.FontWeight.BOLD, size=16)

    def actualizar_visor():
        if not state["pdf_doc"]: return
        doc = state["pdf_doc"]
        pag = state["pdf_pag"]
        
        pix = doc[pag].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5))
        b64_str = base64.b64encode(pix.tobytes()).decode()
        visor_img.src = f"data:image/png;base64,{b64_str}"
        visor_txt_pag.value = f"Página {pag + 1} de {len(doc)}"
        page.update()

    def cambiar_pagina(delta):
        if not state["pdf_doc"]: return
        nueva_pag = state["pdf_pag"] + delta
        if 0 <= nueva_pag < len(state["pdf_doc"]):
            state["pdf_pag"] = nueva_pag
            actualizar_visor()

    def cerrar_visor(e):
        panel_visor.visible = False
        if state["pdf_doc"]:
            state["pdf_doc"].close()
            state["pdf_doc"] = None
        page.update()

    def abrir_visor_pdf(nombre_archivo):
        pdf_bytes = next((b for b, n in state["archivos_procesados"] if n == nombre_archivo), None)
        if pdf_bytes:
            state["pdf_doc"] = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            state["pdf_pag"] = 0
            visor_titulo_text.value = f"Visor de Objetos Digitales: {nombre_archivo}"
            actualizar_visor()
            panel_visor.visible = True
            page.update()

    def mover_visor(e):
        panel_visor.top = max(0, panel_visor.top + e.local_delta.y)
        panel_visor.left = max(0, panel_visor.left + e.local_delta.x)
        panel_visor.update()

    visor_titulo_text = ft.Text("Visor de Documento", size=15, weight=ft.FontWeight.BOLD, color="white", expand=True)

    barra_titulo_visor = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.PICTURE_AS_PDF, color="white", size=18),
                visor_titulo_text,
                ft.IconButton(ft.Icons.CLOSE, icon_color="white", icon_size=18, on_click=cerrar_visor),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=AZUL_UNAM,
        padding=ft.Padding.symmetric(horizontal=15, vertical=10),
        border_radius=ft.BorderRadius(top_left=8, top_right=8, bottom_left=0, bottom_right=0),
    )

    gesto_arrastre_visor = ft.GestureDetector(
        content=barra_titulo_visor,
        mouse_cursor=ft.MouseCursor.MOVE,
        on_pan_update=mover_visor,
    )

    panel_visor = ft.Container(
        content=ft.Column(
            [
                gesto_arrastre_visor,
                ft.Container(
                    content=ft.Column([
                        ft.Container(content=visor_interactivo, expand=True, alignment=ft.Alignment.CENTER),
                        ft.Row([
                            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=lambda e: cambiar_pagina(-1), icon_color=AZUL_UNAM),
                            visor_txt_pag,
                            ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda e: cambiar_pagina(1), icon_color=AZUL_UNAM),
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ]),
                    padding=15,
                    expand=True,
                ),
            ],
            spacing=0,
        ),
        width=750,
        height=750,
        left=150,
        top=40,
        bgcolor="white",
        border=ft.Border.all(1, BORDE),
        border_radius=8,
        shadow=ft.BoxShadow(blur_radius=25, color="#00000040", offset=ft.Offset(0, 10)),
        visible=False,
    )

    def actualizar_dato(indice, columna, nuevo_valor):
        state["datos_editables"][indice][columna] = nuevo_valor

    def construir_tabla_grafica():
        tabla_resultados.columns = [ft.DataColumn(ft.Text(str(c), weight=ft.FontWeight.BOLD)) for c in state["columnas"]]
        nuevas_filas = []
        
        for i, fila in enumerate(state["datos_editables"]):
            celdas = []
            for col in state["columnas"]:
                valor_actual = fila.get(col, "")
                texto_celda = str(valor_actual) if pd.notna(valor_actual) else ""

                if col.lower() == "archivo":
                    celda_control = ft.TextButton(
                        content=ft.Text(texto_celda, size=12, weight=ft.FontWeight.BOLD),
                        on_click=lambda e, n=texto_celda: abrir_visor_pdf(n),
                        style=ft.ButtonStyle(color=AZUL_UNAM, padding=0)
                    )
                else:
                    if state["modo_edicion"]:
                        def crear_callback(idx, c):
                            return lambda e: actualizar_dato(idx, c, e.control.value)
                        
                        celda_control = ft.TextField(
                            value=texto_celda,
                            text_size=12,
                            dense=True,
                            border=ft.InputBorder.UNDERLINE,
                            content_padding=5,
                            on_change=crear_callback(i, col)
                        )
                    else:
                        display_text = texto_celda[:60] + "..." if len(texto_celda) > 60 else texto_celda
                        celda_control = ft.Text(display_text, size=12)
                
                celdas.append(ft.DataCell(celda_control))
            nuevas_filas.append(ft.DataRow(cells=celdas))
        
        tabla_resultados.rows = nuevas_filas
        page.update()

    def toggle_edicion(e):
        state["modo_edicion"] = e.control.value
        construir_tabla_grafica()

    switch_edicion = ft.Switch(label="✏️ Habilitar Edición Manual", value=False, on_change=toggle_edicion, active_color=DORADO_UNAM)

    def reiniciar_flujo(e):
        state["archivos_pendientes"].clear()
        state["archivos_procesados"].clear()
        state["datos_editables"].clear()
        state["modo_edicion"] = False
        switch_edicion.value = False
        
        texto_archivos.value = "No hay documentos en la bandeja."
        texto_archivos.color = "grey"
        boton_iniciar.disabled = True
        consola_log.controls.clear()
        contenedor_principal.content = vista_ingreso
        page.update()

    async def iniciar_flujo(e):
        contenedor_principal.content = vista_monitor
        page.update()

        archivos_a_procesar = []
        for item in state["archivos_pendientes"]:
            contenido = item["bytes"]
            if item["name"].lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                    for f_name in z.namelist():
                        if f_name.lower().endswith(".pdf") and not f_name.startswith("__MACOSX"):
                            archivos_a_procesar.append((z.read(f_name), f_name.split('/')[-1]))
            else:
                archivos_a_procesar.append((contenido, item["name"]))

        state["archivos_procesados"] = archivos_a_procesar
        total = len(archivos_a_procesar)
        resultados = []

        for i, (pdf_bytes, nombre) in enumerate(archivos_a_procesar):
            texto_progreso.value = f"Analizando ({i+1}/{total}): {nombre}"
            indicador_progreso.value = (i) / total
            
            consola_log.controls.append(ft.Text(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando extracción estructurada de {nombre}...", color="#4CAF50", font_family="Consolas"))
            page.update()

            try:
                doc_temp = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                pix = doc_temp[0].get_pixmap(matrix=pymupdf.Matrix(0.3, 0.3))
                b64_str = base64.b64encode(pix.tobytes()).decode()
                imagen_portada.src = f"data:image/png;base64,{b64_str}"
                doc_temp.close()
            except Exception:
                imagen_portada.src = PIXEL_TRANSPARENTE
            page.update()

            meta = await asyncio.to_thread(extraer_metadatos, pdf_bytes)
            meta["archivo"] = nombre 
            resultados.append(meta)

            consola_log.controls.append(ft.Text(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Metadatos extraídos con éxito.", color="white", font_family="Consolas"))
            page.update()

        indicador_progreso.value = 1.0
        texto_progreso.value = "Generando hoja de catalogación..."
        page.update()

        df_crudo = pd.DataFrame(resultados)
        df_limpio = await asyncio.to_thread(preparar_dataframe_para_excel, df_crudo)
        
        state["columnas"] = list(df_limpio.columns)
        state["datos_editables"] = df_limpio.to_dict(orient="records")

        construir_tabla_grafica()
        await asyncio.sleep(0.5) 
        
        contenedor_principal.content = vista_resultados
        page.update()

    # ==========================================
    # MANEJADORES DE SERVICIO DE ARCHIVOS (NUEVO API 0.86+)
    # ==========================================
    async def abrir_explorador(e):
        # FilePicker asíncrono y directo sin llamadas a constructores ni overlays
        archivos = await ft.FilePicker().pick_files(
            allow_multiple=True, 
            allowed_extensions=["pdf", "zip"]
        )
        
        if not archivos: 
            return

        archivos_cargados = []
        for f in archivos:
            if f.path:
                with open(f.path, 'rb') as doc:
                    archivos_cargados.append({"name": f.name, "bytes": doc.read()})

        state["archivos_pendientes"] = archivos_cargados
        texto_archivos.value = f"📚 {len(archivos_cargados)} archivo(s) listo(s) para procesar."
        texto_archivos.color = AZUL_UNAM
        boton_iniciar.disabled = False
        page.update()

    async def preparar_y_guardar_csv(e):
        if state["datos_editables"]:
            df_final = pd.DataFrame(state["datos_editables"])
            csv_buffer = io.BytesIO()
            df_final.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            state["csv_bytes"] = csv_buffer.getvalue()
            
            # Invocar diálogo nativo asíncrono directamente
            ruta = await ft.FilePicker().save_file(
                file_name=f"Catalogacion_BNM_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                allowed_extensions=["csv"],
            )
            
            if ruta:
                with open(ruta, 'wb') as f:
                    f.write(state["csv_bytes"])
                    
                snack = ft.SnackBar(ft.Text(f"Catálogo CSV exportado exitosamente: {ruta}"))
                page.overlay.append(snack)
                snack.open = True
                page.update()

    # ==========================================
    # BOTONES PRINCIPALES
    # ==========================================
    boton_explorar = ft.ElevatedButton(
        "Explorar Documentos",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=abrir_explorador,
        style=ft.ButtonStyle(bgcolor=DORADO_UNAM, color=AZUL_UNAM, padding=20),
    )

    boton_iniciar = ft.ElevatedButton(
        "Iniciar Motor de Extracción",
        icon=ft.Icons.ROCKET_LAUNCH,
        on_click=iniciar_flujo,
        disabled=True,
        style=ft.ButtonStyle(bgcolor=AZUL_UNAM, color="white", padding=20),
    )

    boton_descargar = ft.ElevatedButton(
        "Descargar Metadatos Editados (CSV)",
        icon=ft.Icons.DOWNLOAD,
        on_click=preparar_y_guardar_csv,
        style=ft.ButtonStyle(bgcolor=AZUL_UNAM, color="white", padding=20),
    )

    boton_reiniciar = ft.OutlinedButton(
        "Procesar Nuevo Lote",
        icon=ft.Icons.REFRESH,
        on_click=reiniciar_flujo,
        style=ft.ButtonStyle(color=AZUL_UNAM, padding=20),
    )

    # ==========================================
    # ENSAMBLAJE DE VISTAS
    # ==========================================
    vista_ingreso = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.UPLOAD_FILE, size=80, color=BORDE),
                ft.Text("Carga de Materiales Digitales", size=24, weight=ft.FontWeight.BOLD, color=AZUL_UNAM),
                ft.Text("Selecciona archivos PDF sueltos o un lote comprimido en ZIP.", size=14, color="grey"),
                ft.Container(height=20),
                boton_explorar,
                texto_archivos,
                ft.Container(height=30),
                boton_iniciar,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )

    vista_monitor = ft.Container(
        content=ft.Column(
            [
                ft.Text("Procesamiento de Lenguaje Natural en Curso", size=20, weight=ft.FontWeight.BOLD, color=AZUL_UNAM),
                indicador_progreso,
                texto_progreso,
                ft.Divider(color=BORDE),
                ft.Row(
                    [
                        ft.Container(
                            content=imagen_portada,
                            border=ft.Border.all(1, BORDE),
                            border_radius=8,
                            padding=10,
                            bgcolor="white",
                        ),
                        ft.Container(
                            content=consola_log,
                            expand=True,
                            bgcolor="#1E1E1E",
                            border_radius=8,
                            padding=15,
                        ),
                    ],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            ]
        ),
        padding=30,
        expand=True,
    )

    vista_resultados = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color="#155724", size=30),
                            ft.Text("Extracción Semántica Completada", size=24, weight=ft.FontWeight.BOLD, color="#155724"),
                        ]),
                        switch_edicion 
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Container(
                    content=ft.Row([tabla_resultados], scroll=ft.ScrollMode.ALWAYS),
                    expand=True,
                    border=ft.Border.all(1, BORDE),
                    border_radius=8,
                ),
                ft.Row([boton_reiniciar, boton_descargar], alignment=ft.MainAxisAlignment.END, spacing=15)
            ]
        ),
        padding=30,
        expand=True,
    )

    contenedor_principal = ft.AnimatedSwitcher(
        content=vista_ingreso,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=400,
        expand=True,
    )

    page.add(
        ft.Stack(
            [
                contenedor_principal,
                panel_visor,
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.run(main)