import pandas as pd

def calcular_huella_carbono(df_ifc, hojas_bbdd, etapas):
    """
    Calcula la huella de carbono por material en base a las etapas seleccionadas y la base de datos.

    df_ifc: DataFrame con columnas ['Material', 'Cantidad', 'Unidad', 'ID']
    hojas_bbdd: Diccionario de hojas del Excel de sostenibilidad
    etapas: Lista de etapas seleccionadas (e.g. ['A1-3', 'A4-A5', 'C1', 'C2', 'C3', 'C4', 'D'])

    Devuelve un DataFrame con los cálculos.
    """

    # Unificar hojas relevantes (A1-3, A4-A5, C-D)
    hojas_uso = ['A1-3', 'A4-A5', 'C', 'D']
    base = pd.concat(
        [hojas_bbdd[h].copy().assign(etapa=h) for h in hojas_uso if h in hojas_bbdd],
        ignore_index=True
    )

    base = base.dropna(subset=['Nombre', 'GWP', 'Ud'])  # Solo filas con datos clave

    # Normalizar nombres de materiales
    base['Nombre'] = base['Nombre'].astype(str).str.lower().str.strip()
    df_ifc['Material'] = df_ifc['Material'].astype(str).str.lower().str.strip()

    # Agrupar por material y etapa
    resultados = []

    for material in df_ifc['Material'].unique():
        filas_material = df_ifc[df_ifc['Material'] == material]
        cantidad_total = filas_material['Cantidad'].sum()

        fila_resultado = {
            'Material': material.title(),
            'Cantidad [m³]': round(cantidad_total, 4)
        }

        total_huella = 0

        for etapa in etapas:
            etapa_nombre = etapa if etapa != 'A4-5' else 'A4-A5'
            if etapa_nombre == 'A1-3':
                hoja_etapa = base[base['etapa'] == 'A1-3']
            elif etapa_nombre == 'A4-5':
                hoja_etapa = base[base['etapa'] == 'A4-A5']
            elif etapa_nombre == 'D':
                hoja_etapa = base[base['etapa'] == 'D']
            else:
                hoja_etapa = base[base['etapa'] == 'C']

            # Buscar GWP para el material
            posibles = hoja_etapa[hoja_etapa['Nombre'].str.contains(material.lower(), case=False)]

            if posibles.empty:
                valor_gwp = 0
            else:
                valor_gwp = posibles['GWP'].mean()

            etapa_col = f"GWP {etapa} [kg CO₂ eq/m³]"
            fila_resultado[etapa_col] = round(valor_gwp, 2)
            total_huella += valor_gwp * cantidad_total

        fila_resultado['Huella Total [kg CO₂ eq]'] = round(total_huella, 2)
        resultados.append(fila_resultado)

    return pd.DataFrame(resultados)
