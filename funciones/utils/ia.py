import streamlit as st
import google.generativeai as genai

def cargar_modelo():
    """
    Carga el modelo generativo de Gemini usando la clave en st.secrets.
    """
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ No se encontró GOOGLE_API_KEY en los secrets de Streamlit.")
    
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel("gemini-1.5-pro-latest")

    return modelo
