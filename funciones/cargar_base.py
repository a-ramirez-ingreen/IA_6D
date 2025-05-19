import pandas as pd
import os

def cargar_todas_las_hojas(ruta_excel="datos/00 - Base datos DIGITAEC v2.xlsx"):
    """
    Carga todas las hojas de un archivo Excel como DataFrames en un diccionario.
    Ignora hojas vacías y normaliza encabezados.
    """
    if not os.path.exists(ruta_excel):
        return {"error": f"No se encontró el archivo: {ruta_excel}"}

    try:
        hojas_crudas = pd.read_excel(ruta_excel, sheet_name=None, header=None)
        hojas_limpias = {}

        for nombre_hoja, df in hojas_crudas.items():
            if df.empty or df.shape[0] < 4:
                continue  # Ignorar hojas con menos de 4 filas

            df.columns = df.iloc[1]  # Asignar la fila 2 como encabezado real
            df = df.iloc[3:].reset_index(drop=True)  # Saltar las primeras filas con info de títulos/unidades

            if df.shape[1] > 1:
                hojas_limpias[nombre_hoja] = df

        return hojas_limpias if hojas_limpias else {"error": "No se encontraron hojas con datos válidos."}

    except Exception as e:
        return {"error": f"Error al leer el archivo Excel: {e}"}
