#import re
#import fitz
#from collections import Counter
#import spacy
#from unidecode import unidecode
#from .motor_ia import extraer_temas_con_qwen, arreglar_titulo_con_qwen
#from datetime import datetime

import os
import re
import fitz
import pandas as pd
#from typing import List, Dict, Optional, Tuple
#from collections import defaultdict
from collections import Counter
import spacy
from datetime import datetime
from unidecode import unidecode
import streamlit as st
#from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

# --- TUS CONSTANTES ORIGINALES ---
MAX_PORTADA_PAGES = 3
MAX_LEGAL_PAGES = 6
MIN_TITLE_LEN = 8
MAX_TITLE_LEN = 120
MIN_SUBTITLE_LEN = 2
MAX_SUBTITLE_LEN = 60
MIN_AUTHOR_LEN = 5

NUM_LETRAS_A_NUM = {
    "primera": "1a.", "primer": "1a.", "segunda": "2a.", "segundo": "2a.",
    "tercera": "3a.", "tercer": "3a.", "cuarta": "4a.", "cuarto": "4a.",
    "quinta": "5a.", "quinto": "5a.", "sexta": "6a.", "sexto": "6a.",
    "séptima": "7a.", "séptimo": "7a.", "octava": "8a.", "octavo": "8a.",
    "novena": "9a.", "noveno": "9a.", "décima": "10a.", "décimo": "10a."
}

PATRONES_COLECCION = [
    r"colección[:\s]+([^\n.,;]+)",
    r"serie[:\s]+([^\n.,;]+)",
    r"colección\s+\"([^\"]+)\"",
    r"serie\s+\"([^\"]+)\"",
    r"colección\s+([^\n.,;]+)\)",
    r"serie\s+([^\n.,;]+)\)",
    r"colección\s+([^\n.,;]+)=",
    r"serie\s+([^\n.,;]+)=",
    r"\(colección\s+([^\n.,;]+)=",
    r"\(serie\s+([^\n.,;]+)="
]

PALABRAS_CLAVE_LEGAL = [
    "isbn", "depósito legal", "copyright", "todos los derechos reservados",
    "edición", "ed.", "ed ", "editorial", "impreso en", "primera edición",
    "segunda edición", "traducción", "autor", "reimpresión", "catalogacion",
    "catalogación", "@", "©", "www", "en trámite", "en tramite",
    "registro en trámite", "registro en tramite"
]

PALABRAS_CLAVE_CORTE = [
    "índice", "indice", "contenido", "prólogo", "prologo", "introducción",
    "introduccion", "capítulo", "capitulo", "presentación", "presentacion",
    "temas", "repertorio", "prefacio", "programa", "sumario", "dedicado a",
    "dedicatoria", "agradecimiento", "agradecimientos"
]

# 1. Calculamos la ruta real (dinámica) de la carpeta principal del proyecto o del ejecutable
RUTA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Construimos las rutas absolutas a las carpetas de los modelos
RUTA_MODELO_BASE = os.path.join(RUTA_RAIZ, "modelo_base_es")
RUTA_MODELO_FINETUNED = os.path.join(RUTA_RAIZ, "modelo_finetuned_ner_lg")

@st.cache_resource
def load_nlp_model():
    try:
        return spacy.load(RUTA_MODELO_BASE)
    except Exception as e:
        print(f"Error cargando el modelo base en {RUTA_MODELO_BASE}: {e}")
        return None

nlp = load_nlp_model()

@st.cache_resource
def load_nlp_model_finetuned():
    try:
        return spacy.load(RUTA_MODELO_FINETUNED)
    except Exception as e:
        print(f"Error cargando el modelo finetuned en {RUTA_MODELO_FINETUNED}: {e}")
        return None

nlp_finetuned = load_nlp_model_finetuned()

# --- TODAS TUS FUNCIONES DE BLOQUES Y PÁGINAS ---
def process_block(block, page_num):
    """Procesa un renglón de texto conservando la información de posición y estilo del renglón"""
    font_sizes = []

    is_bold = False

    line_details = []

    for line in block.get("lines", []):
        line_text = ""
        line_fonts = []
        font_sizes = []

        for span in line.get("spans", []):
            span_text = span.get("text", "").strip()

            if span_text:
                line_text += span_text

                line_fonts.append({
                    "size": span["size"],
                    "font": span["font"],
                    "text": span_text
                })

                if "bold" in span["font"].lower():
                    is_bold = True

                font_sizes.append(span["size"])

        if line_text:

            avg_size = sum(font_sizes)/len(font_sizes) if font_sizes else 0
            max_size = max(font_sizes) if font_sizes else 0

            is_upper = line_text.upper() == line_text

            line_details.append({
                "text": line_text.strip(),
                "y_pos": line["bbox"][1],
                "x_pos": line["bbox"][0],
                "avg_size": avg_size,
                "max_size": max_size,
                "is_bold": is_bold,
                "is_upper": is_upper,
                "spans": line_fonts
            })

    return line_details


def procesar_bloques_pagina(page, page_num):
    """
    Procesa todos los renglones de una página devolviendo una lista con renglones
    procesados de una página en concreto
    """
    bloques = []

    for block in page.get_text("dict").get("blocks", []):
        block_data = process_block(block, page_num)
        if block_data:
            bloques.extend(block_data)
    return bloques


def contar_claves_en_texto(texto, lista_claves):
    """
    Cuenta cuantas palabras clave de una lista tiene una página
    """
    return sum(1 for palabra in lista_claves if palabra in texto)


def extraer_bloques_por_pagina(pdf_path, max_paginas=12):
    """
    Procesa los bloques de texto desde la portada hasta justo antes del contenido.
    """

    doc = fitz.open(stream=pdf_path, filetype="pdf")
    bloques_por_pagina = {}

    pagina_legal = None
    pagina_corte = None

    for page_num in range(min(len(doc), max_paginas)):
        page = doc[page_num]
        text = page.get_text().lower()

        # Detectar hoja legal
        if pagina_legal is None:
            num_claves_legales = contar_claves_en_texto(text, PALABRAS_CLAVE_LEGAL)
            if num_claves_legales >= 2:
                pagina_legal = page_num
                bloques = procesar_bloques_pagina(page, page_num)
                if bloques:
                    bloques_por_pagina[page_num] = bloques
                continue

        # Después de la hoja legal, busca la página de inicio de contenido
        if pagina_legal is not None and page_num > pagina_legal:
            num_claves_corte = contar_claves_en_texto(text, PALABRAS_CLAVE_CORTE)
            if num_claves_corte >= 1:
                pagina_corte = page_num
                break

        # Extrae los bloques de texto de una página
        bloques = procesar_bloques_pagina(page, page_num)
        if bloques:
            bloques_por_pagina[page_num] = bloques

    doc.close()
    return bloques_por_pagina


def limpiar_texto_pdf(texto):
    """
    Limpia el texto extraído del PDF, uniendo palabras divididas por guión + salto de línea.
    También puede eliminar múltiples espacios y saltos de línea innecesarios.
    """

    # Reemplaza guiones (U+00AD) con nada
    texto = texto.replace('\xad*\n*', '')

    # Une palabras partidas por guión y salto de línea
    texto = re.sub(r'-\s*\n\s*', '', texto)

    # Une palabras partidas por guión y salto de línea
    texto = re.sub(r'(?<=\w)\n(?=\w)', ' ', texto)
    texto = re.sub(r'\n', '', texto)

    return texto.strip()

def extraer_pagina_hoja_legal(pdf_path, max_paginas=12):
    """
    Extrae el texto plano de la hoja legal, detectada por palabras clave.
    """
    doc = fitz.open(stream=pdf_path, filetype="pdf")

    for page_num in range(min(len(doc), max_paginas)):
        page = doc[page_num]
        text = page.get_text().lower()
        num_claves_legales = contar_claves_en_texto(text, PALABRAS_CLAVE_LEGAL)

        if num_claves_legales >= 2:
            doc.close()
            return page_num

    doc.close()
    return None

def extraer_texto_hoja_legal(pdf_path, max_paginas=12):
    """
    Extrae el texto plano de la hoja legal, detectada por palabras clave.
    """
    doc = fitz.open(stream=pdf_path, filetype="pdf")

    for page_num in range(min(len(doc), max_paginas)):
        page = doc[page_num]
        text = page.get_text().lower()
        num_claves_legales = contar_claves_en_texto(text, PALABRAS_CLAVE_LEGAL)

        if num_claves_legales >= 2:
            doc.close()
            return limpiar_texto_pdf(text)

    doc.close()
    return ""

def extraer_texto_desde_paginas_procesadas(pdf_path, paginas_procesadas):
    """
    Extrae el texto plano combinado de todas las páginas procesadas.
    """
    doc = fitz.open(stream=pdf_path, filetype="pdf")
    texto_total = ""

    for pagina in sorted(set(paginas_procesadas)):
        if pagina < len(doc):
            texto_total += doc[pagina].get_text() + " \n "

    doc.close()
    return limpiar_texto_pdf(texto_total)


def formatear_texto(texto):
    # 1. Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto.strip())

    # 2. Pasar todo a minúsculas
    texto = texto.lower()

    # 3. Capitalizar inicio de oraciones
    resultado = ""
    capitalizar = True

    for char in texto:
        if capitalizar and char.isalpha():
            resultado += char.upper()
            capitalizar = False
        else:
            resultado += char

        if char in ".!?¿¡":
            capitalizar = True

    # 4. Procesar con spaCy para detectar entidades
    #nlp = load_nlp_model()
    doc = nlp(resultado)

    # 5. Reemplazar entidades por versión capitalizada
    texto_final = resultado
    offset = 0  # para manejar cambios de longitud

    for ent in doc.ents:
        if ent.label_ not in ["PER", "LOC", "ORG"]:
          continue

        inicio = ent.start_char + offset
        fin = ent.end_char + offset

        entidad_original = texto_final[inicio:fin]
        entidad_corregida = entidad_original.title()

        texto_final = (
            texto_final[:inicio] +
            entidad_corregida +
            texto_final[fin:]
        )

        offset += len(entidad_corregida) - len(entidad_original)

    return texto_final

def limpiar_y_formatear(texto):
    if texto is None:
        return None
    texto = str(texto).strip()
    if not texto:
        return None
    return formatear_texto(texto)

# --- TUS FUNCIONES DE LÓGICA ESPECÍFICA ---
def estilo(linea):
    """
    Extrae el estilo principal de un renglón.
    """
    font = linea["spans"][0]["font"] if linea["spans"] else ""
    return {
        "max_size": round(linea["max_size"], 1),
        "is_bold": linea["is_bold"],
        "is_upper": linea["is_upper"],
        "font": font
    }

def estilos_similares(est1, est2, tolerancia_size=0.3):
    """
    Compara dos estilos y devuelve un booleano si son similares o no.
    """
    size_similar = abs(est1["max_size"] - est2["max_size"]) <= tolerancia_size
    same_font = est1["font"] == est2["font"]
    bold_match = est1["is_bold"] == est2["is_bold"]
    upper_match = est1["is_upper"] == est2["is_upper"]

    return size_similar and same_font and bold_match and upper_match


def agrupar_lineas(lineas, multiplicador_distancia=1.5):
    """
    Agrupa renglones procesados, de acuerdo a su estilo, cercania
    o características similares para obtener bloques de texto similares.
    """
    if not lineas:
        return []

    bloques = []
    # Ordenar lineas
    lineas = sorted(lineas, key=lambda x: (x["y_pos"], x["x_pos"]))

    bloque_actual = {
        "text": lineas[0]["text"],
        "lines_details": [lineas[0]]
    }

    for i in range(1, len(lineas)):
        linea_ant = bloque_actual["lines_details"][-1]
        linea_sig = lineas[i]

        est_ant = estilo(linea_ant)
        est_sig = estilo(linea_sig)

        son_estilos_similares = estilos_similares(est_ant, est_sig)

        distancia_vertical = linea_sig["y_pos"] - (linea_ant["y_pos"] + linea_ant["max_size"])

        limite_distancia = est_ant["max_size"] * multiplicador_distancia
        esta_cerca = distancia_vertical <= limite_distancia

        if son_estilos_similares and esta_cerca:
            bloque_actual["text"] += " " + linea_sig["text"]
            bloque_actual["lines_details"].append(linea_sig)
        else:
            bloques.append(bloque_actual)
            bloque_actual = {
                "text": linea_sig["text"],
                "lines_details": [linea_sig]
            }

    if bloque_actual["lines_details"]:
        bloques.append(bloque_actual)
    return bloques


#------ Extraccion de metadatos -------

# ISBN
def extraer_isbns(texto):
    encontrados, resultados = set(), []
    patron = re.compile(r"(?P<tipo>\be?isbn(?:[^\d\n]{0,20})?)[\s:–-]*(?P<isbn>(?:97[89][-\s]?\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?[\dXx])|(?:\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?[\dXx]))", re.IGNORECASE | re.VERBOSE)
    for match in patron.finditer(texto):
        tipo_raw = match.group("tipo").strip()
        isbn_limpio = re.sub(r"[\s-]", "", match.group("isbn"))
        if 9 <= len(isbn_limpio) <= 14:
            clave = (tipo_raw.lower(), isbn_limpio.upper())
            if clave not in encontrados:
                encontrados.add(clave)
                resultados.append(tipo_raw + ' ' + isbn_limpio.upper())
    patron_tramite = re.compile(r"\b(?P<tipo>e?isbn|registro)[\s:–-]*(?P<estado>en\s+(tr[aá]mite|proceso|espera|gesti[oó]n)|pendiente)\b", re.IGNORECASE | re.VERBOSE)
    for match in patron_tramite.finditer(texto):
        estado = match.group("estado").strip().lower()
        clave = (match.group("tipo").strip().lower(), estado)
        if clave not in encontrados:
            encontrados.add(clave)
            resultados.append("ISBN: " + estado)
    return resultados



def normalizar_texto(texto):
    """
    Limpia el texto para extraer el título.
    """
    texto = unidecode(texto).lower()
    texto = re.sub(r'[^\w\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def es_candidato_valido_titulo(texto):
    """
    Determina si un texto puede ser un candidato válido a título.
    Filtra textos demasiado cortos, demasiado largos o metadatos como:
    ISBN, copyright, URLs, notas editoriales, etc.
    También excluye cadenas compuestas solo por números.
    """
    if not texto:
        return False

    if len(texto) < MIN_TITLE_LEN or len(texto) > MAX_TITLE_LEN:
        return False

    texto_min = texto.lower()

    excluir = [
        "isbn", "copyright", "derechos reservados", "www.", "http",
        "impreso", "todos los autores", "creative commons", "editorial"
    ]

    if any(p in texto_min for p in excluir):
        return False

    # Rechazar números o símbolos
    if re.match(r'^[\d\s\-\.:]+$', texto):
        return False

    # Debe tener al menos una palabra
    if len(texto.split()) < 1:
        return False

    return True


def textos_relacionados(texto1, texto2):
    """
    Determina si dos textos están relacionados usando:
    - Coincidencia de substrings normalizados
    - Intersección mínima de palabras clave
    """
    n1 = normalizar_texto(texto1)
    n2 = normalizar_texto(texto2)

    if n1 in n2 or n2 in n1:
        return True

    palabras1 = set(n1.split())
    palabras2 = set(n2.split())
    if not palabras1 or not palabras2:
        return False

    comunes = palabras1.intersection(palabras2)
    return len(comunes) >= min(2, len(palabras1), len(palabras2))


def calcular_puntaje_prominencia(texto, bloque, pagina):
    """
    Calcula un puntaje que mide cuán prominente es un bloque de texto.
    Se basa en:
    - Tamaño máximo de fuente (muy relevante)
    - Tamaño promedio
    - Posición vertical en la página (más arriba = más prominente)
    - Negrita
    - Número de página (las primeras valen más)
    - Longitud adecuada del texto
    """
    puntaje = 0
    lineas = bloque.get("lines_details", [])
    if not lineas:
        return puntaje

    sizes = [l["max_size"] for l in lineas]
    avg_size = sum(sizes) / len(sizes)
    max_size = max(sizes)

    y_positions = [l["y_pos"] for l in lineas]
    y_top = min(y_positions)

    puntaje += max_size * 20
    puntaje += avg_size * 8

    if y_top > 90:
        puntaje += 60

    if any(l["is_bold"] for l in lineas):
        puntaje += 10

    if pagina == 0:
        puntaje = 0
    elif pagina == 1:
        puntaje += 60
    elif pagina == 2:
        puntaje += 60
    elif pagina == 3:
        puntaje += 20
    elif pagina > 3:
        puntaje += 10

    if MIN_TITLE_LEN <= len(texto) <= MAX_TITLE_LEN:#5 - 120
        puntaje += 10


    return puntaje

def encontrar_titulo_mas_prominente(bloques_agrupados):
    """
    Busca entre las primeras 5 páginas el bloque con mayor puntaje de prominencia.
    Solo considera candidatos válidos a título.
    Devuelve el bloque más probable como título.
    """
    candidatos = []

    for pagina_info in bloques_agrupados:
        pagina = pagina_info["pagina"]
        if pagina > 5:
            continue

        for bloque in pagina_info["bloques"]:
            texto = bloque["text"].strip()

            if not es_candidato_valido_titulo(texto):
                continue

            puntaje = calcular_puntaje_prominencia(texto, bloque, pagina)
            candidatos.append((puntaje, pagina, bloque))

    if not candidatos:
        return None

    candidatos.sort(reverse=True, key=lambda x: x[0])

    return candidatos[0][2]


def buscar_version_completa_en_paginas(titulo_base, bloque_base, bloques_agrupados):
    """
    Dado un título base, busca en las primeras 5 páginas si hay
    una versión más larga o completa:
    - Basado en coincidencia normalizada
    - Basado en textos relacionados
    Devuelve la versión más larga encontrada.
    """
    titulo_norm = normalizar_texto(titulo_base)

    mejor_titulo = titulo_base
    mejor_len = len(titulo_base)

    for pagina_info in bloques_agrupados:
        if pagina_info["pagina"] > 5:
            continue

        for bloque in pagina_info["bloques"]:
            texto = bloque["text"].strip()
            if not es_candidato_valido_titulo(texto):
                continue

            t_norm = normalizar_texto(texto)

            if titulo_norm in t_norm and len(texto) > mejor_len:
                mejor_titulo = texto
                mejor_len = len(texto)
                continue

    return mejor_titulo


def extraer_titulo(bloques_agrupados):
    """
    Extrae el título del documento:
    - Encuentra el bloque más prominente
    - Busca una versión más completa del mismo en otras páginas
    """
    bloque_titulo = encontrar_titulo_mas_prominente(bloques_agrupados)
    if not bloque_titulo:
        return None

    titulo_base = bloque_titulo["text"].strip()

    titulo_final = buscar_version_completa_en_paginas(
        titulo_base, bloque_titulo, bloques_agrupados
    )

    return titulo_final



# ------------- subtitulo-----------

def extraer_subtitulo(bloque_titulo, pagina_titulo, titulo_final, bloques_agrupados):
    """
    Busca un subtítulo basado en:
    - Tamaño de fuente (75%–95% del título)
    - Estar debajo del título en la misma página
    - Relación semántica con el título
    - Longitud mínima y máxima
    Devuelve el mejor candidato encontrado.
    """
    detalles = bloque_titulo["lines_details"]
    titulo_y_bottom = max(l["y_pos"] for l in detalles)
    titulo_avg = sum(l["max_size"] for l in detalles) / len(detalles)

    mejor = None
    mejor_score = 0

    id_pagina_titulo = pagina_titulo["pagina"] if pagina_titulo else -1
    otras_paginas = [p for p in bloques_agrupados if 0 <= p["pagina"] <= 5 and p["pagina"] != id_pagina_titulo]
    paginas = ([pagina_titulo] if pagina_titulo else []) + otras_paginas

    for pagina_info in paginas:
        for bloque in pagina_info["bloques"]:
            if bloque is bloque_titulo:
                continue

            texto = bloque["text"].strip()
            palabras = texto.split()
            if len(palabras) < MIN_SUBTITLE_LEN or len(palabras) > MAX_SUBTITLE_LEN:
                continue

            sizes = [l["max_size"] for l in bloque["lines_details"]]
            avg = sum(sizes) / len(sizes)
            ratio = avg / titulo_avg

            if ratio < 0.65 or ratio > 0.95:
                continue

            if pagina_info is pagina_titulo:
                y_top = min(l["y_pos"] for l in bloque["lines_details"])


                distancia_vertical = y_top - titulo_y_bottom
                if distancia_vertical > (titulo_avg * 3.5):
                    continue

                if y_top <= titulo_y_bottom:
                    continue

            related = textos_relacionados(titulo_final, texto)

            score = (1 - abs(0.9 - ratio))
            if related:
                score += 0.1

            if score > mejor_score:
                mejor_score = score
                mejor = texto

    return mejor

def limpiar_texto_fuerte(texto):
    if not texto:
        return texto

    # eliminar caracteres de control
    texto = re.sub(r'[\x00-\x1F\x7F]', '', texto)

    # normalizar espacios
    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip()

def separar_subtitulo(titulo):
    """
    Separa subtitulo del titulo si hay ':' o '.'.
    Retorna (titulo_recortado, subtitulo) o (titulo, None)
    """
    if not titulo:
        return titulo, None

    titulo_clean = re.sub(r'[\u200b\xa0]', ' ', titulo).strip()

    # Buscar último ':' o '.' con algo de texto después
    match = re.search(r'[:\.]\s*(\S.+)$', titulo_clean)
    if match:
        subtitulo_cand = match.group(1).strip()

        # mínimo 2 palabras
        if len(subtitulo_cand.split()) < 2:
            return titulo_clean, None

        palabras_sub = set(subtitulo_cand.split())
        palabras_titulo = set(titulo_clean.split())
        overlap = len(palabras_sub & palabras_titulo) / len(palabras_sub)
        if overlap > 0.7:
            return titulo_clean, None

        # evitar abreviaturas o números con puntos
        if re.match(r'^[A-Z]{1,3}\.$', subtitulo_cand) or re.match(r'^\d+(\.\d+)+$', subtitulo_cand):
            return titulo_clean, None

        # subtitulo válido, recortar título
        titulo_recortado = titulo_clean[:match.start()].strip()
        return titulo_recortado, subtitulo_cand

    return titulo_clean, None

def subtitulo_es_titulo(subtitulo, titulo_final):
    """
    Retorna True si más de la mitad de las palabras del subtitulo
    aparecen en el titulo_final, indicando que probablemente no sea un subtitulo real.
    """
    if not subtitulo or not titulo_final:
        return False

    subtitulo = limpiar_y_formatear(subtitulo)
    titulo_final = limpiar_y_formatear(titulo_final)

    palabras_sub = set(subtitulo.split())
    palabras_titulo = set(titulo_final.split())

    if not palabras_sub:
        return False

    overlap = len(palabras_sub & palabras_titulo) / len(palabras_sub)
    return overlap > 0.5

def extraer_titulo_y_subtitulo(bloques_agrupados):
    """
    Función principal:
    - Extrae título
    - Separa subtítulo del título si hay ':' o '.'
    - Si no hay subtítulo derivado, busca subtítulo en bloques
    """
    bloque_titulo = encontrar_titulo_mas_prominente(bloques_agrupados)
    if not bloque_titulo:
        return {"titulo": None, "subtitulo": None}

    titulo_completo = extraer_titulo(bloques_agrupados)
    titulo_clean = re.sub(r'[\u200b\xa0]', ' ', titulo_completo).strip()


    subtitulo = None
    titulo_final = titulo_clean

    match = re.search(r'[:\.]\s*(\S.+)$', titulo_clean)
    if match:
        idx = match.start()
        titulo_final = titulo_clean[:idx].strip()
        subtitulo = titulo_clean[idx+1:].strip()
    else:
        titulo_final = titulo_clean
        subtitulo = None
        pagina_titulo = next((p for p in bloques_agrupados if bloque_titulo in p["bloques"]), None)
        subtitulo = extraer_subtitulo(bloque_titulo, pagina_titulo, titulo_final, bloques_agrupados)
        subtitulo = limpiar_texto_fuerte(subtitulo)
        titulo_final = limpiar_texto_fuerte(titulo_final)
        if subtitulo_es_titulo(subtitulo, titulo_final):
            subtitulo = None

    if subtitulo:
        palabras = subtitulo.split()
        if len(palabras) < MIN_SUBTITLE_LEN or len(palabras) > MAX_SUBTITLE_LEN:
            subtitulo = None

    return {
        "titulo": limpiar_y_formatear(titulo_final),
        "subtitulo": limpiar_y_formatear(subtitulo)
    }

# ----autores----------

def limpiar_texto_para_autores(texto):
    """
    Preprocesamiento el texto plano para extraer autores.
    """
    # Escudo de seguridad por si el texto llega vacío desde antes
    if not texto: return ""
    
    texto = re.sub(r'(?<=\w)\n(?=\w)', ' ', texto)
    texto = re.sub(r'\n+', '\n', texto)
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', '. ', texto)
    texto = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', ' ', texto)
    
    return texto.strip()

def formatear_nombre_autor(nombre):
    partes = nombre.strip().split()

    if len(partes) < 2:
        return nombre

    if len(partes) >= 3:
        apellidos = " ".join(partes[-2:])
        nombres = " ".join(partes[:-2])
    else:
        apellidos = partes[-1]
        nombres = partes[0]

    return f"{apellidos}, {nombres}"

def extraer_autores(texto, titulo, subtitulo):
    # 🛑 DESTRUCTOR DE D.R. DEFINITIVO (Evita fusiones con apellidos)
    texto = re.sub(r'D\.?R\.?', ' ', texto, flags=re.IGNORECASE)
    
    texto_limpio = limpiar_texto_para_autores(texto)
    if not texto_limpio.strip():
        return []

    doc = nlp(texto_limpio)
    autores = []
    
    PALABRAS_PROHIBIDAS = {
        "derechos", "humanos", "declaración", "universal", "difusión", 
        "subdirector", "director", "secretaría", "departamento", 
        "edición", "consejo", "instituto", "colegio", "universidad",
        "facultad", "comité", "dirección", "nacional", "autónoma", "gobierno"
    }
    
    # 🛑 ESCUDO: ROLES QUE NO SON AUTORÍA INTELECTUAL
    ROLES_SECUNDARIOS = [
        "traductor", "traductores", "traducción", "traducido",
        "diseño", "corrección", "formación", "estilo", "revisión", 
        "portada", "ilustración", "ilustrador", "ilustraciones", 
        "fotografía", "cuidado", "fotógrafo", "diagramación", "coordinación"
    ]
    
    TITULOS_ACADEMICOS = [r'\bdr\.?\b', r'\bdra\.?\b', r'\blic\.?\b', r'\bing\.?\b', 
                          r'\bmtro\.?\b', r'\bmtra\.?\b', r'\bprof\.?\b', r'\bprofa\.?\b']

    for ent in doc.ents:
        if ent.label_ != "PER":
            continue

        nombre = ent.text.strip()
        
        # 🛑 ANÁLISIS DE CONTEXTO (Ignora el nombre si hay roles secundarios cerca)
        inicio = max(0, ent.start_char - 80)
        fin = min(len(texto_limpio), ent.end_char + 80)
        contexto = texto_limpio[inicio:fin].lower()
        
        if any(rol in contexto for rol in ROLES_SECUNDARIOS):
            continue
            
        for titulo_ac in TITULOS_ACADEMICOS:
            nombre = re.sub(titulo_ac, '', nombre, flags=re.IGNORECASE)
            
        nombre = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', '', nombre).strip()

        palabras_nombre = nombre.split()
        if len(palabras_nombre) < 2 or len(palabras_nombre) > 5:
            continue

        if not (MIN_AUTHOR_LEN <= len(nombre) <= 50):
            continue

        nombre_lower = nombre.lower()
        if titulo and nombre_lower in titulo.lower(): continue
        if subtitulo and nombre_lower in subtitulo.lower(): continue

        if any(p in nombre_lower for p in PALABRAS_PROHIBIDAS):
            continue

        nombre_norm = re.sub(r'\s+', ' ', nombre).strip().title()

        es_duplicado = False
        for i, autor_existente in enumerate(autores):
            set_nuevo = set(nombre_norm.split())
            set_existente = set(autor_existente.split())
            
            if len(set_nuevo & set_existente) / min(len(set_nuevo), len(set_existente)) > 0.6:
                if len(nombre_norm) > len(autor_existente):
                    autores[i] = nombre_norm
                es_duplicado = True
                break
                
        if not es_duplicado:
            autores.append(nombre_norm)

    return autores

def clasificar_autores(texto, titulo, subtitulo):
    autores = extraer_autores(texto, titulo, subtitulo)

    if not autores:
        return {
            "autor_principal": None,
            "coautores": []
        }

    texto_lower = texto.lower()

    autor_principal = None
    if not autor_principal:
        autor_principal = autores[0]

    coautores = [a for a in autores if a != autor_principal]

    # Formatear salida
    autor_principal_fmt = formatear_nombre_autor(autor_principal)
    coautores_fmt = [formatear_nombre_autor(a) for a in coautores]

    return {
        "autor_principal": autor_principal_fmt,
        "coautores": coautores_fmt[:5]
    }

# ------- edicion ------------------

def normalizar_ordinal_basico(texto):
    """
    Convierte la edición encontrada en un mismo formato.
    """
    texto = texto.lower().strip()
    if texto in NUM_LETRAS_A_NUM:
        return NUM_LETRAS_A_NUM[texto]
    num_match = re.match(r"(\d{1,2})\s?(a|ra|da|ta|ª)?\.?", texto)
    if num_match:
        return f"{num_match.group(1)}a."
    return None

def extraer_ediciones(texto):
    """
    Extrae posibles ediciones del texto.
    """
    texto = texto.lower().replace("edicion", "edición")
    resultados = set()

    patron = re.compile(
        r"(\d{1,2}\s?(?:a|ra|da|ta|ª)?\.?|primera|primer|segunda|segundo|tercera|tercer|cuarta|cuarto|quinta|quinto|sexta|sexto|séptima|séptimo|octava|octavo|novena|noveno|décima|décimo)[\s.,:-]{0,3}edición",
        re.IGNORECASE
    )

    for match in patron.findall(texto):
        ordinal = normalizar_ordinal_basico(match)
        if ordinal:
            resultados.add(f"{ordinal} edición")

    if resultados:
      return sorted(resultados)
    else:
      return None
    


# ----------lugar publicacion ---------

#def extraer_lugar_publicacion(texto):
#    if not texto: return None
#    texto = texto.lower()
#    if "impreso en méxico" in texto or "ciudad de méxico" in texto or "méxico, d.f" in texto: return "México"
#    for p in [r"impreso en\s+([a-záéíóúñ\s]+)(?:,|\.|[0-9]|\n)", r"lugar de edición[:\s]+([a-záéíóúñ\s]+)(?:,|\.|[0-9]|\n)", r"editado en\s+([a-záéíóúñ\s]+)(?:,|\.|[0-9]|\n)"]:
#        match = re.search(p, texto)
#        if match and 3 < len(match.group(1).strip()) < 40: return match.group(1).strip().title()
#    return None

def extraer_lugar_publicacion(texto):
    """
    Extrae lugares del texto plano de las páginas procesadas limpiando basura final.
    """
    texto_limpio = limpiar_texto_para_autores(texto)
    doc = nlp_finetuned(texto_limpio)
    lugares = set()

    for ent in doc.ents:
        if ent.label_ == "LUGAR_PUBLICACION":
            nombre = ent.text.strip()
            
            # Elimina números y símbolos al final de la cadena
            nombre = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', '', nombre).strip()
            
            if len(nombre) > 3:
                lugares.add(nombre.title())

    return sorted(lugares)

# -------------- editorial -------------
#def extraer_editorial(texto):
#    if not texto: return None
#    if "estadística y geografía" in texto.lower() or "inegi" in texto.lower(): return "Instituto Nacional de Estadística y Geografía (INEGI)"
#    if "discriminación" in texto.lower() and "consejo" in texto.lower(): return "Consejo Nacional para Prevenir la Discriminación"
#    for p in [r"(?:editorial|editado por|coedición)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+)(?:\s+en\s+|,|\.|\n)", r"©\s*\d{4}[,\s]+([A-ZÁÉÍÓÚÑ][^\n.,;]+)"]:
#        match = re.search(p, texto, re.IGNORECASE)
#        if match and 4 < len(match.group(1).strip()) < 100: return match.group(1).strip().title()
#    for inst in ["Secretaría de", "Universidad", "Instituto", "Comisión", "Fondo de Cultura"]:
#        if inst.lower() in texto.lower(): return inst.title()
#    return None

def extraer_editorial(texto):
    """
    Extrae editoriales y elimina duplicados superpuestos.
    """
    texto_limpio = limpiar_texto_para_autores(texto)
    doc = nlp_finetuned(texto_limpio)
    editoriales = []

    for ent in doc.ents:
        if ent.label_ == "EDITORIAL":
            nombre = ent.text.strip()
            # Limpiar basura final
            nombre = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', '', nombre).strip()
            
            # Quitar palabras genéricas al inicio
            nombre = re.sub(r'^(editorial|ediciones|editores)\s+', '', nombre, flags=re.IGNORECASE).strip()
            
            # 🛑 FILTRO ANTI-DIRECCIONES
            nombre = re.sub(r'\s+\b(Av|Avenida|Col|Colonia|Esq|Esquina|Sur|Norte|Calle|C\.|C\.\s*P\.)\b.*$', '', nombre, flags=re.IGNORECASE).strip()
            
            if nombre.lower() == 'inegi' or len(nombre) < 4:
                continue
                
            nombre_norm = nombre.title()
            
            es_duplicado = False
            for i, ed in enumerate(editoriales):
                if nombre_norm in ed:
                    es_duplicado = True
                    break
                elif ed in nombre_norm:
                    editoriales[i] = nombre_norm
                    es_duplicado = True
                    break
                    
            if not es_duplicado:
                editoriales.append(nombre_norm)

    return sorted(editoriales)

#----------------- año------------

def buscar_anio(texto):
    anio_maximo = min(datetime.now().year, 2050)
    todos_los_anos = re.findall(r"\b(19[0-9]{2}|20[0-4][0-9]|2050)\b", texto)
    contador_anos = Counter(todos_los_anos)
    excluidos = {match[1] for match in re.compile(r"(Dep[oó]sito\s*Legal|D\.?L\.?|DL)[^\n\r\d]{0,10}?(19[0-9]{2}|20[0-4][0-9]|2050)", re.IGNORECASE).findall(texto)}
    validos = [anio for anio in set(todos_los_anos) if int(anio) <= anio_maximo and (anio not in excluidos or contador_anos[anio] > 1)]
    return sorted(set(validos), key=int)[-1] if validos else None

def extraer_anio_publicacion(texto_legal, texto_total):
    return buscar_anio(texto_legal) or buscar_anio(texto_total)

# --------------- paginacion -------------

import fitz

def extraer_numero_paginas(pdf_path):
    """
    Devuelve el último folio (página membretada) encontrado en las páginas finales del PDF.
    Si no encuentra un folio válido, devuelve el total de páginas físicas como respaldo.
    """
    try:
        doc = fitz.open(stream=pdf_path, filetype="pdf")
        total_paginas_fisicas = len(doc)
        
        # Si el documento es un folleto muy corto, es más seguro devolver el total físico
        if total_paginas_fisicas < 5:
            doc.close()
            return total_paginas_fisicas

        ultimo_folio = None
        
        # Revisamos las últimas 15 páginas de atrás hacia adelante
        limite_revision = max(-1, total_paginas_fisicas - 16)
        
        for i in range(total_paginas_fisicas - 1, limite_revision, -1):
            pagina = doc[i]
            bloques = pagina.get_text("dict").get("blocks", [])
            
            for bloque in bloques:
                if bloque.get("type") == 0:  # Verifica que el bloque sea de texto, no imagen
                    for linea in bloque.get("lines", []):
                        for span in linea.get("spans", []):
                            texto = span.get("text", "").strip()
                            
                            # 1. Verificamos que el texto sea un número
                            if texto.isdigit():
                                posible_folio = int(texto)
                                
                                # 2. VALIDACIÓN DE LÓGICA:
                                # Evita confundir el año de impresión (ej. 2026) o un número 
                                # de teléfono con un folio. El folio real debe estar cerca del total físico.
                                # Aquí damos una tolerancia de 40 páginas (por índices, anexos, etc.).
                                if (total_paginas_fisicas - 40) <= posible_folio <= (total_paginas_fisicas + 2):
                                    ultimo_folio = posible_folio
                                    break
                        if ultimo_folio: break
                if ultimo_folio: break
            if ultimo_folio: break
            
        doc.close()
        
        # Si encontró un folio válido, lo devuelve. Si no, usa el total físico como plan B.
        return ultimo_folio if ultimo_folio else total_paginas_fisicas
        
    except Exception as e:
        print(f"Error al contar páginas: {e}")
        return None

def extraer_paginacion(pdf_path):
    """
    Devuelve la paginación del archivo PDF.
    """
    try:
        total_paginas = extraer_numero_paginas(pdf_path)
        paginacion = f'{total_paginas} páginas'
        return paginacion
    except Exception as e:
        print(f"Error al extraer paginación: {e}")
        return None

# ---------------- coleccion ------------------

def coleccion_serie(texto):
    """
    Busca en el texto plano de las páginas procesadas patrones para encontrar la colección o serie.
    """
    texto = texto.lower()
    posibles = set()

    for patron in PATRONES_COLECCION:
        for match in re.findall(patron, texto, flags=re.IGNORECASE):

            nombre = re.sub(r"[^a-zA-Z0-9\s:]", "", match).strip().title()
            if 4 <= len(nombre) <= 120:
                posibles.add(nombre)

    return sorted(posibles)

def extraer_coleccion_serie_aux(texto):
    """
    Extrae la coleccion o serie de un texto.
    """
    posibles = set()

    texto_limpio = limpiar_texto_pdf(texto)

    # Primero busca en el texto legal
    coleccion = coleccion_serie(texto_limpio)
    if coleccion:
        posibles.update(coleccion)
    return sorted({formatear_texto(re.split(r'[\s\n]+', p)[0]) for p in posibles if p})

def extraer_coleccion_serie(texto_legal, texto_total):
    """
    Extrae la coleccion o serie, buscando primero en el texto de la hoja legal
    y luego en el texto total de las páginas procesadas.
    """
    coleccion = extraer_coleccion_serie_aux(texto_legal)
    if coleccion:
      for col in coleccion:
        if 4 <= len(col) <= 120:
          return coleccion

    coleccion = extraer_coleccion_serie_aux(texto_total)
    if coleccion:
      for col in coleccion:
        if 4 <= len(col) <= 120:
          return coleccion

    return None


# --- TU FUNCIÓN ORQUESTADORA PRINCIPAL ---
def extraer_metadatos(pdf_path):
    """Extrae todos los metadatos del libro en PDF, realizando todos los procesos necesarios."""

    # Diccionario con los posibles metadatos de un libro en concreto
    metadatos = {
        "archivo": pdf_path,
        "isbns": [],
        "titulo": None,
        "subtitulo": None,
        "autor_principal": None,
        "coautores": [],
        "ediciones": [],
        "lugares": [],
        "editoriales": [],
        "anio_publicacion": None,
        "num_paginas": None,
        "coleccion": None
    }

    try:
        # Extrae bloques de las páginas relevantes del libro
        bloques_por_pagina = extraer_bloques_por_pagina(pdf_path)

        # Agrupa los bloques obtenidos por estilo
        bloques_agrupados = []
        paginas_procesadas = list(bloques_por_pagina.keys())

        pagina_legal = extraer_pagina_hoja_legal(pdf_path)

        for pagina, lineas in bloques_por_pagina.items():
          # Convertimos pagina a int por si viene como string en el diccionario
          pagina_actual = int(pagina)

          # Verificamos si pagina_legal existe antes de comparar
          if pagina_legal is not None and pagina_actual == int(pagina_legal):
              continue  # Es la página legal, la ignoramos

          # Si llegamos aquí, NO es la página legal (o no se detectó ninguna)
          agrupados = agrupar_lineas(lineas)
          bloques_agrupados.append({
              "pagina": pagina_actual,
              "bloques": agrupados
          })

        # Obtiene el texto plano de todas las páginas procesadas
        texto_total = extraer_texto_desde_paginas_procesadas(pdf_path, paginas_procesadas)

        # Obtiene el texto plano de la hoja legal
        texto_legal = extraer_texto_hoja_legal(pdf_path)

        # Si no encuentra la hoja legal, entonces toma todo el texto
        texto_legal = texto_total if not texto_legal else texto_legal

        # Extrae los ISBNs que haya
        isbn_info = extraer_isbns(texto_legal)
        metadatos["isbns"] = isbn_info if isbn_info else None

        titulo_subtitulo = extraer_titulo_y_subtitulo(bloques_agrupados)

        # Extrae el título
        titulo = titulo_subtitulo["titulo"]
        metadatos["titulo"] = titulo if titulo else None

        # Extrae el subtítulo
        subtitulo = titulo_subtitulo["subtitulo"]
        metadatos["subtitulo"] = subtitulo if subtitulo else None

        # Extrae los autores
        autores = clasificar_autores(texto_total, titulo, subtitulo)

        autor_principal = autores["autor_principal"]
        metadatos["autor_principal"] = autor_principal if autor_principal else None

        coautores = autores["coautores"]
        metadatos["coautores"] = coautores if coautores else None

        # Extrae la o las ediciones
        ediciones = extraer_ediciones(texto_legal)
        metadatos["ediciones"] = ediciones if ediciones else None

        # Extrae el o los posibles lugares de publicación, obteniendo el estado de la publicación
        lugar_pub = extraer_lugar_publicacion(texto_legal)
        metadatos["lugares"] = lugar_pub if lugar_pub else None

        # Extrae a lo más 3 editoriales
        editoriales = extraer_editorial(texto_legal)
        metadatos["editoriales"] = editoriales if editoriales else None

        # Extrae el año de publicación
        anio_publicacion = extraer_anio_publicacion(texto_legal, texto_total)
        metadatos["anio_publicacion"] = anio_publicacion if anio_publicacion else None

        # Extrae el número de páginas
        paginas = extraer_paginacion(pdf_path)
        metadatos["num_paginas"] = paginas if paginas else None

        # Extrae la colección o serie
        coleccion = extraer_coleccion_serie(texto_legal, texto_total)
        metadatos["coleccion"] = coleccion if coleccion else None

    except Exception as e:
        print(f"Error procesando {pdf_path}: {e}")
        import traceback
        traceback.print_exc()

    return metadatos
