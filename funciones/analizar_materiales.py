import pandas as pd
import os

def analizar_volumen_por_material(ruta_csv):
    """
    Analiza un CSV exportado del IFC y retorna un DataFrame con volumen total por material.
    Guarda el CSV con resumen por material.
    """
    if not os.path.isfile(ruta_csv):
        raise FileNotFoundError(f"Archivo CSV no encontrado: {ruta_csv}")

    df = pd.read_csv(ruta_csv)

    claves_material = ["material", "pset_material", "tipo_material", "nombre_material"]
    claves_volumen = ["volumen", "volume", "pset_volumen", "cantidad_volumen", "vol_total", "cantidad"]

    def encontrar_columna(df, posibles_nombres):
        for col in df.columns:
            for clave in posibles_nombres:
                if clave in str(col).lower():
                    return col
        return None

    col_material = encontrar_columna(df, claves_material)
    col_volumen = encontrar_columna(df, claves_volumen)

    if not col_material or not col_volumen:
        raise ValueError("No se encontró columna de material o volumen.")

    df[col_volumen] = pd.to_numeric(df[col_volumen], errors="coerce")
    df["Material"] = df[col_material].astype(str).str.strip()
    df = df.dropna(subset=["Material", col_volumen])

    df_resultado = df.groupby("Material")[col_volumen].sum().reset_index()
    df_resultado.columns = ["Material", "Volumen_Total"]

    output_path = os.path.join(os.path.dirname(ruta_csv), "materiales_volumen_detallado.csv")
    df_resultado.to_csv(output_path, index=False)

    return df_resultado, output_path
