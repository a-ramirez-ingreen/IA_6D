import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()  # Cargar variables desde .env

def cargar_modelo():
    """
    Carga el modelo generativo de Gemini usando la clave de entorno GOOGLE_API_KEY.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ No se encontró GOOGLE_API_KEY en el archivo .env")
    
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel("gemini-1.5-pro-latest")

    return modelo
