import re
from openai import OpenAI

# 1. Configuración del cliente Qwen (Conexión al servidor GIL UNAM)
# Nota: El usuario debe estar conectado manualmente a la VPN con FortiClient.
qwen_client = OpenAI(
    base_url="http://132.247.131.251:8000/v1", 
    api_key="dummy-key"
)

# 2. Funciones de Extracción con IA
def extraer_temas_con_qwen(texto_total):
    if not texto_total: return None
    
    try:
        texto_analisis = texto_total[:3000]
        prompt = f"""
        Eres un catalogador experto de la Biblioteca Nacional de México.
        Analiza el siguiente extracto de un libro y sugiere de 1 a 3 temas o palabras clave que lo describan.
        Responde ÚNICAMENTE con los temas separados por comas, sin introducciones ni texto extra.
        
        Extracto del libro:
        {texto_analisis}
        """
        
        response = qwen_client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, 
            max_tokens=50
        )
        
        temas_qwen = response.choices[0].message.content.strip()
        temas_qwen = temas_qwen.replace("Temas:", "").replace("Palabras clave:", "").strip()
        return temas_qwen.rstrip('.').title()
        
    except Exception as e:
        print(f"⚠️ Qwen no disponible (Temas): {e}")
        # Respaldo Regex
        patron = r"(?:palabras clave|temas|keywords|descriptores)[:\s]+([^\n]+)"
        match = re.search(patron, texto_total, re.IGNORECASE)
        if match:
            temas = match.group(1).strip().rstrip('.')
            if 3 < len(temas) < 150: return temas.capitalize()
        return None

def arreglar_titulo_con_qwen(titulo_crudo):
    if not titulo_crudo or len(titulo_crudo.split()) < 2: 
        return titulo_crudo
        
    try:
        prompt = f"""
        Eres un experto en corrección de estilo editorial. El siguiente texto es el título de un libro, pero sus palabras están desordenadas. 
        Ordena las palabras para que el título tenga sentido lógico y gramatical en español.
        Responde ÚNICAMENTE con el título corregido, sin comillas, sin explicaciones.
        
        Título desordenado: {titulo_crudo}
        """
        
        response = qwen_client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return titulo_crudo