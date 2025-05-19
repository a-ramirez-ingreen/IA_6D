import pandas as pd
from io import StringIO
from funciones.utils.ia import cargar_modelo

def normalizar_materiales_con_ia(df_ifc, hojas_bbdd):
    """
    Usa IA para mapear materiales del IFC a nombres equivalentes en la base de sostenibilidad.
    Añade una nueva columna 'Material_Normalizado'.
    """
    modelo = cargar_modelo()

    materiales_unicos = df_ifc['Material'].dropna().unique().tolist()
    nombres_bbdd = set()
    for hoja in hojas_bbdd.values():
        if 'Nombre' in hoja.columns:
            nombres_bbdd.update(hoja['Nombre'].dropna().astype(str).str.strip())

    ejemplos = """
Ejemplos comunes:
- "HA-30/B/20/IIa" → "Hormigón armado HA-30"
- "B500S" → "Acero corrugado B500"
- "XPS 100" → "Poliestireno extruido"
- "A-42" → "Acero laminado A-42"
- "EPS grafito" → "Poliestireno expandido grafito"
"""

    prompt = f"""
Eres un experto en materiales de construcción. Tienes que interpretar nombres técnicos de materiales que provienen de modelos BIM (IFC), muchos de ellos escritos en formatos normativos, con siglas, abreviaciones o formas mixtas.

Tu objetivo es identificar el material que realmente representa cada uno de estos, y buscar su equivalente más cercano en una base de datos ambiental de sostenibilidad.

{ejemplos}

### Lista de materiales del modelo IFC:
{chr(10).join('- ' + m for m in materiales_unicos)}

### Lista de nombres válidos en la base de datos:
{chr(10).join('- ' + n for n in sorted(nombres_bbdd))}

Para cada material del modelo IFC, responde con el nombre más cercano y coherente de la base de datos, aunque esté escrito de forma distinta.

Si no encuentras uno razonable, escribe "NO ENCONTRADO".

Devuelve los resultados en una tabla Markdown con dos columnas exactas:
Material_IFC | Material_Normalizado
"""

    respuesta = modelo.generate_content(prompt).text

    try:
        tabla = pd.read_table(StringIO(respuesta), sep='|', engine='python')
        tabla.columns = [col.strip() for col in tabla.columns]
        tabla['Material_IFC'] = tabla['Material_IFC'].str.strip()
        tabla['Material_Normalizado'] = tabla['Material_Normalizado'].str.strip()
        mapeo = dict(zip(tabla['Material_IFC'], tabla['Material_Normalizado']))
        df_ifc['Material_Normalizado'] = df_ifc['Material'].map(mapeo).fillna("NO ENCONTRADO")
    except Exception as e:
        print("❌ Error interpretando la tabla de la IA:", e)
        df_ifc['Material_Normalizado'] = "NO ENCONTRADO"

    return df_ifc
