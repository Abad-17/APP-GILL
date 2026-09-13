import pandas as pd
import io
import re
import spacy
import difflib
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

def load_nlp_model():
    try:
        return spacy.load("es_core_news_lg")
    except:
        return None


def limpiar_listas_para_excel(df):
    """
    Convierte listas en el DataFrame a cadenas separadas por comas,
    sin corchetes ni comillas.
    """
    for columna in df.columns:
        df[columna] = df[columna].apply(lambda x: '; '.join(x) if isinstance(x, list) else x)
    return df

def limpiar_caracteres_ilegales_excel(texto):
    """
    Limpia los caracteres no aceptados por Excel.
    """
    if isinstance(texto, str):
        return ILLEGAL_CHARACTERS_RE.sub('', texto)
    return texto

def preparar_dataframe_para_excel(df):
    """
    Realiza la limpieza necesaria para que el DataFrame pueda ser exportado a Excel
    y que no salga con caracteres ilegales o comillas y corchetes.
    """
    for columna in df.columns:
        def procesar(x):
            if isinstance(x, list):
                x = list(dict.fromkeys(x))  # Elimina duplicados preservando orden
                return limpiar_caracteres_ilegales_excel('; '.join(x))
            return limpiar_caracteres_ilegales_excel(x)

        df[columna] = df[columna].apply(procesar)
    return df


def estructurar_y_exportar_catalogacion(df_crudo, ruta_autoridades):
    #nlp = load_nlp_model()
    # --- INICIO DE BÚSQUEDA SEMÁNTICA (FUZZY MATCHING) ---
    #mapa_autoridades = {}
    #try:
    #    df_auth = pd.read_excel(ruta_autoridades)
        # Extraemos la lista original respetando mayúsculas y acentos
    #    temas_originales = df_auth[df_auth.columns[0]].astype(str).str.replace(r'^\$a\s*', '', regex=True).str.strip().tolist()
        # Creamos un diccionario {texto_en_minusculas: texto_original_oficial}
    #    mapa_autoridades = {t.lower(): t for t in temas_originales if t.lower() != 'nan'}
    #except Exception as e:
    #    print(f"Advertencia: No se pudo cargar el catálogo de autoridades. {e}")

    # --- FIN DE BÚSQUEDA SEMÁNTICA ---

    def limpiar_isbn(isbn):
        if pd.isna(isbn): return ""
        return re.sub(r'[-\s]', '', str(isbn))

    def formatear_titulo(titulo):
        if pd.isna(titulo) or not nlp: return ""
        texto = str(titulo).strip().lower()
        doc = nlp(texto)
        tokens = [t.text.capitalize() if t.ent_type_ else t.text for t in doc]
        resultado = " ".join(tokens)
        if not resultado: return ""
        resultado = resultado[0].upper() + resultado[1:]
        articulos = ["El ", "La ", "Los ", "Las ", "Un ", "Una ", "Unos ", "Unas "]
        for art in articulos:
            if resultado.lower().startswith(art.lower()):
                resto = resultado[len(art):].strip()
                if resto: resultado = f"{resto[0].upper() + resto[1:]}, {art.strip().capitalize()}"
                break
        return resultado

    def estructurar_nombres(autor_str):
        if pd.isna(autor_str): return ""
        autor_str = str(autor_str).replace('.', '').strip()
        if not autor_str: return ""
        if ',' in autor_str: return autor_str 
        conectores = {"de", "la", "las", "el", "los", "del", "y", "san", "santa", "mac", "mc", "van", "von"}
        partes_originales = autor_str.split()
        partes_agrupadas, temp = [], []
        for palabra in partes_originales:
            if palabra.lower() in conectores: temp.append(palabra)
            else:
                if temp:
                    temp.append(palabra)
                    partes_agrupadas.append(" ".join(temp))
                    temp = []
                else: partes_agrupadas.append(palabra)
        if len(partes_agrupadas) >= 3: return f"{' '.join(partes_agrupadas[-2:])}, {' '.join(partes_agrupadas[:-2])}"
        elif len(partes_agrupadas) == 2: return f"{partes_agrupadas[1]}, {partes_agrupadas[0]}"
        return autor_str
    
    def formatear_paginacion(pag):
        if pd.isna(pag) or str(pag).strip() == "": return ""
        pag_str = str(pag).strip()
        if "página" in pag_str.lower() or "pag" in pag_str.lower(): return pag_str
        if pag_str.isdigit(): return f"{pag_str} páginas"
        return pag_str

    def extraer_autor_principal(autores):
        if pd.isna(autores) or not autores: return ""
        lista_autores = [a.strip() for a in str(autores).split(',') if a.strip()]
        return estructurar_nombres(lista_autores[0]) if lista_autores else ""

    def extraer_coautores(autores):
        if pd.isna(autores) or not autores: return ""
        lista_autores = [a.strip() for a in str(autores).split(',') if a.strip()]
        return " ; ".join([estructurar_nombres(a) for a in lista_autores[1:]]) if len(lista_autores) > 1 else ""

    df_final = pd.DataFrame(columns=['ISBN', 'TÍTULO', 'SUBTÍTULO', 'AUTOR PRINCIPAL', 'COAUTOR(ES)', 'NÚMERO DE EDICIÓN', 'LUGAR DE PUBLICACIÓN', 'EDITORIAL', 'AÑO', 'PAGINACIÓN', 'COLECCIÓN O SERIE'])
    
    df_final['ISBN'] = df_crudo.get('isbns', pd.Series())#.apply(limpiar_isbn)
    df_final['TÍTULO'] = df_crudo.get('titulo', pd.Series())#.apply(formatear_titulo)
    df_final['SUBTÍTULO'] = df_crudo.get('subtitulo', pd.Series())#.apply(formatear_titulo)
    df_final['AUTOR PRINCIPAL'] = df_crudo.get('autor_principal', pd.Series())#.apply(extraer_autor_principal)
    df_final['COAUTOR(ES)'] = df_crudo.get('coautores', pd.Series())#.apply(extraer_coautores)
    df_final['NÚMERO DE EDICIÓN'] = df_crudo.get('ediciones', pd.Series())
    df_final['LUGAR DE PUBLICACIÓN'] = df_crudo.get('lugares', pd.Series()) 
    df_final['EDITORIAL'] = df_crudo.get('editoriales', pd.Series())
    df_final['AÑO'] = df_crudo.get('anio_publicacion', pd.Series())
    df_final['PAGINACIÓN'] = df_crudo.get('num_paginas', pd.Series())#.apply(formatear_paginacion)
    df_final['COLECCIÓN O SERIE'] = df_crudo.get('coleccion', pd.Series())
    #if 'temas' in df_crudo.columns: df_final['TEMAS / PALABRAS CLAVE'] = df_crudo['temas'].apply(validar_tema)

    buffer = io.BytesIO()
    writer = pd.ExcelWriter(buffer, engine='xlsxwriter')
    nombre_hoja = 'Lista_Materiales'
    df_final.to_excel(writer, sheet_name=nombre_hoja, startrow=2, index=False)
    
    workbook, worksheet = writer.book, writer.sheets[nombre_hoja]
    formato_cabecera = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'center', 'align': 'center', 'bg_color': '#D9D9D9', 'border': 1})
    for col_num, value in enumerate(df_final.columns.values):
        worksheet.write(2, col_num, value, formato_cabecera)
        worksheet.set_column(col_num, col_num, 25) 
        
    worksheet.write('A1', 'BIBLIOTECA NACIONAL DE MÉXICO - DEPARTAMENTO DE ADQUISICIONES', workbook.add_format({'bold': True, 'font_size': 12}))
    worksheet.write('A2', 'Lista de materiales a entregar (Extracción Automatizada)', workbook.add_format({'italic': True, 'font_size': 11}))
    writer.close()
    return buffer