import pandas as pd

def postprocesar_huella(df_ia, ids_ifc):
    """
    Asegura que todos los IDs del IFC estén presentes en el DataFrame final.
    Si faltan elementos, se añaden con Total=0 y Unidad constante.
    """
    if not isinstance(df_ia, pd.DataFrame):
        raise ValueError("df_ia debe ser un DataFrame")
    
    # Asegurar columnas mínimas
    if not all(col in df_ia.columns for col in ['ID', 'Total', 'Unidad']):
        raise ValueError("Las columnas esperadas son: ['ID', 'Total', 'Unidad']")

    df_ia['ID'] = df_ia['ID'].astype(str).str.strip()
    df_ia['Total'] = pd.to_numeric(df_ia['Total'], errors='coerce').fillna(0)
    
    # Unidad uniforme
    unidad = df_ia['Unidad'].mode().iloc[0] if not df_ia['Unidad'].isna().all() else "kg CO₂ eq"
    df_ia['Unidad'] = unidad

    # IDs faltantes
    ids_actuales = set(df_ia['ID'])
    ids_faltantes = [id_ for id_ in ids_ifc if id_ not in ids_actuales]

    # Crear filas faltantes
    filas_faltantes = pd.DataFrame({
        'ID': ids_faltantes,
        'Total': 0,
        'Unidad': unidad
    })

    # Unir y devolver
    df_final = pd.concat([df_ia, filas_faltantes], ignore_index=True)
    return df_final
