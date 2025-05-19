import pandas as pd

def formatear_hojas_para_ia(hojas_dict, max_filas_por_hoja=25):
    """
    Convierte cada hoja de la base de datos en texto Markdown interpretable por IA.
    Incluye encabezados y algunos valores reales de ejemplo.
    """
    partes = []

    for nombre_hoja, df in hojas_dict.items():
        try:
            if df.empty or df.shape[1] < 2:
                continue

            n_filas = df.shape[0]
            total_partes = (n_filas // max_filas_por_hoja) + 1

            for i in range(total_partes):
                inicio = i * max_filas_por_hoja
                fin = min((i + 1) * max_filas_por_hoja, n_filas)
                df_chunk = df.iloc[inicio:fin]

                # Convertir a markdown visual
                texto_md = df_chunk.to_markdown(index=False)
                partes.append(f"### Hoja: {nombre_hoja} (filas {inicio + 1} - {fin})\n{texto_md}")
        except Exception as e:
            partes.append(f"### Hoja: {nombre_hoja} (⚠️ Error al procesar: {e})")

    return "\n\n".join(partes)
