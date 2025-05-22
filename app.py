# ===============================================================
# 01 --- IMPORTACIONES Y CONFIGURACIÓN GENERAL -----------------------
# ===============================================================
import streamlit as st
import os
import pandas as pd
from io import BytesIO

from funciones.cargar_base import cargar_todas_las_hojas
from funciones.analizar_materiales import analizar_volumen_por_material
from funciones.utils.ia import cargar_modelo
from funciones.utils.formatear_hojas_para_ia import formatear_hojas_para_ia
from funciones.procesar_ifc_con_progreso import procesar_ifc
from funciones.agregar_huella_ifc import agregar_huella_ifc

st.set_page_config(page_title="Huella de Carbono IFC", layout="wide")

# ===============================================================
# 02 --- FUNCIÓN: Exportar tabla a Excel -----------------------------
# ===============================================================
def exportar_tabla_excel(markdown: str, nombre_archivo: str):
    import re
    bloques = markdown.split('\n\n')
    tabla_md = None
    for bloque in bloques:
        if bloque.strip().startswith('|') and bloque.strip().count('|') > 2:
            tabla_md = bloque.strip()
            break
    if not tabla_md:
        st.warning("❗ No se detectó ninguna tabla Markdown válida para exportar.")
        return
    try:
        df = pd.read_table(BytesIO(tabla_md.encode()), sep='|', engine='python')
        df = df.dropna(axis=1, how='all').iloc[1:-1].copy()
        df.columns = [col.strip() for col in df.columns]
        df = df.fillna(0)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Huella Carbono', index=False)
        output.seek(0)
        return output
    except Exception as e:
        st.error(f"❌ Error al procesar la tabla Markdown: {e}")
        return None

# ===============================================================
# 03 --- BOTÓN: Reiniciar estado -------------------------------------
# ===============================================================
if st.button(" Reiniciar análisis"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ===============================================================
# 04 --- TÍTULO Y CARGA BASE DE DATOS --------------------------------
# ===============================================================
st.title(" Herramienta de Cálculo de Huella de Carbono IFC")
st.markdown("**Carga automática de base de datos y análisis de materiales del archivo IFC.**")

if "hojas_sostenibilidad" not in st.session_state:
    hojas = cargar_todas_las_hojas("datos/00 - Base datos DIGITAEC v2.xlsx")
    if hojas and "error" not in hojas:
        st.session_state.hojas_sostenibilidad = hojas
        st.success("✅ Base de datos cargada correctamente (v2)")
    else:
        st.error("❌ Error al cargar la base de datos")
        st.stop()

# ===============================================================
# 05 --- INSTRUCCIONES INICIALES Y CARGA DE IFC ----------------------
# ===============================================================
st.markdown("""
### ❔ ¿Cómo empezar?
1.  Sube tu archivo `.IFC`
2.  Se procesará automáticamente
3.  La IA identificará qué propiedades usar
4.  Luego elige qué deseas analizar
""")

archivo_ifc = st.file_uploader("Sube tu archivo IFC", type=["ifc"])

# ===============================================================
# 06 --- PROCESAMIENTO DEL ARCHIVO IFC -------------------------------
# ===============================================================
if archivo_ifc is not None:
    nombre_actual = archivo_ifc.name
    if "ultimo_ifc" not in st.session_state or st.session_state.ultimo_ifc != nombre_actual:
        st.session_state.ultimo_ifc = nombre_actual
        ruta_guardado = os.path.join("subidos", nombre_actual)
        st.session_state["ruta_guardado"] = ruta_guardado
        os.makedirs("subidos", exist_ok=True)
        with open(ruta_guardado, "wb") as f:
            f.write(archivo_ifc.getbuffer())

        progress_bar = st.progress(0)
        with st.spinner(" Procesando IFC completo..."):
            df_ifc = procesar_ifc(ruta_guardado, carpeta_salida="resultados", update_progress=progress_bar.progress)

        st.success("✅ IFC procesado correctamente")

        st.markdown("###  Datos extraídos del IFC")
        st.dataframe(df_ifc.head(15))

        st.markdown("###  Procesamiento por IA para columnas clave")

        fila_ejemplo = None
        for _, fila in df_ifc.iterrows():
            if fila.dropna().shape[0] >= 2:
                fila_ejemplo = fila
                break

        if fila_ejemplo is None:
            st.error("❌ No se encontró un elemento con datos suficientes para usar como ejemplo.")
            st.dataframe(df_ifc.head(10))
            st.stop()

        propiedades_ejemplo = "\n".join([f"- {col}: {fila_ejemplo[col]}" for col in fila_ejemplo.index if pd.notna(fila_ejemplo[col])])
        tipo_elemento = fila_ejemplo.get("Tipo", "Desconocido")
        nombre_elemento = fila_ejemplo.get("Nombre", "Sin nombre")
        guid_elemento = fila_ejemplo.get("ID", "Sin ID")

# ===============================================================
# 07 --- DETECCIÓN DE COLUMNAS CON IA --------------------------------
# ===============================================================
        prompt_identificar = f"""
Analiza las siguientes propiedades reales extraídas de un elemento IFC.
Elemento IFC: {tipo_elemento}
Nombre: {nombre_elemento}
GlobalId: {guid_elemento}

Propiedades detectadas:
{propiedades_ejemplo}

Tu tarea es identificar qué campo corresponde a:
- material_col
- cantidad_col
- unidad_col
- guid_col

⚠️ Si no encuentras columna de unidad o cantidad, o hay campos vacíos, deduce el valor más probable a partir de otras propiedades como longitud, sección, peso, etc. Unifica todo en las columnas indicadas.
Devuelve solo estas líneas con los nombres exactos de las propiedades:
material_col: ...
cantidad_col: ...
unidad_col: ...
guid_col: ...
"""

        modelo = cargar_modelo()
        with st.spinner(" Consultando IA para detectar columnas clave..."):
            respuesta = modelo.generate_content(prompt_identificar).text

        columnas_detectadas = {}
        for linea in respuesta.strip().splitlines():
            if ":" in linea:
                clave, valor = linea.split(":", 1)
                columnas_detectadas[clave.strip()] = valor.strip()

        material_col = columnas_detectadas.get("material_col")
        cantidad_col = columnas_detectadas.get("cantidad_col")
        unidad_col = columnas_detectadas.get("unidad_col")
        guid_col = columnas_detectadas.get("guid_col")

        columnas_validas = [c for c in [material_col, cantidad_col, unidad_col, guid_col] if c in df_ifc.columns]
        df_filtrado = df_ifc[columnas_validas].copy()

        rename_map = {material_col: "Material", cantidad_col: "Cantidad", guid_col: "ID"}
        if unidad_col and unidad_col in df_ifc.columns:
            rename_map[unidad_col] = "Unidad"
        df_filtrado.rename(columns=rename_map, inplace=True)

        st.session_state.df_filtrado = df_filtrado
        st.rerun()

# ===============================================================
# 08 --- INTERFAZ DE FILTRADO Y ANÁLISIS -----------------------------
# ===============================================================
if "df_filtrado" in st.session_state:
    df = st.session_state.df_filtrado
    st.markdown("###  Datos filtrados por IA")
    st.dataframe(df)

    with st.expander(" Seleccionar materiales a analizar"):
        materiales = df['Material'].dropna().unique().tolist()
        all_selected = st.checkbox("Seleccionar todos los materiales", value=True, key="select_all_materials")
        seleccionados = materiales if all_selected else []
        cols = st.columns(4)
        for i, material in enumerate(materiales):
            if all_selected or cols[i % 4].checkbox(material, key=material):
                if material not in seleccionados:
                    seleccionados.append(material)

    st.markdown("###  Selección de etapas del ciclo de vida")
    etapas_disponibles = ["A1-3", "A4", "A5", "C1", "C2", "C3", "C4", "D"]
    seleccionar_todo = st.checkbox("Seleccionar todas las etapas", value=True, key="select_all_etapas")
    etapas_seleccionadas = []
    cols_etapas = st.columns(len(etapas_disponibles))
    for i, etapa in enumerate(etapas_disponibles):
        if seleccionar_todo or cols_etapas[i].checkbox(etapa, key=f"etapa_{etapa}", value=False):
            etapas_seleccionadas.append(etapa)

    if "A4" in etapas_seleccionadas:
        st.markdown("####  ¿Conoces los kilómetros de transporte para A4?")
        km = st.number_input("Introduce distancia en km", min_value=0.0, step=1.0, key="input_km")
        st.session_state["distancia_km"] = km

# ===============================================================
# 09 --- GENERACIÓN DE HUELLA DE CARBONO -----------------------------
# ===============================================================
    if st.button(" Calcular huella de carbono"):
        modelo = cargar_modelo()
        df_analizar = df[df['Material'].isin(seleccionados) if seleccionados else df.index].copy()
        markdown_sostenibilidad = formatear_hojas_para_ia(st.session_state.hojas_sostenibilidad, max_filas_por_hoja=30)
        km_str = f"\nDistancia A4: {st.session_state.get('distancia_km', 'No especificada')} km" if "A4" in etapas_seleccionadas else ""

        # Dividir en bloques de 20
        chunk_size = 20
        bloques = [df_analizar.iloc[i:i+chunk_size] for i in range(0, len(df_analizar), chunk_size)]
        respuesta_total = ""

        for i, bloque in enumerate(bloques):
            markdown_tabla = bloque.to_markdown(index=False)

            prompt = f"""
Actúa como experto ambiental.
Con los datos del modelo IFC (material, cantidad, unidad, ID) y la base de sostenibilidad (etapas A1-3, A4-A5, C, D):

### IFC:
{markdown_tabla}

### Base de sostenibilidad:
{markdown_sostenibilidad}

Etapas seleccionadas: {etapas_seleccionadas}
{km_str}

1. Usa los valores de la columna 'Cantidad' para el cálculo.
Si la unidad es m³, interpreta como volumen.
2. Si algún valor falta, asigna 0.
3. Genera una única tabla con columnas claras:
- ID (GlobalId del elemento IFC)
- Material
- Cantidad [unidad]
- GWP por etapa [kg CO₂ eq/unidad]
- Total

⚠️ IMPORTANTE:
- Solo incluye la línea de encabezado en la PRIMERA parte.
- NO incluyas líneas Markdown de alineación (como `:--`, `--:`, etc.) fuera de la primera tabla.
- NO repitas encabezados en las partes siguientes.
- NO agregues texto antes o después de la tabla.
"""

            with st.spinner(f" Consultando IA (parte {i+1}/{len(bloques)})..."):
                parte = modelo.generate_content(prompt).text
                respuesta_total += parte.strip() + "\n"

        # ---------------------------------------------------------
        # LIMPIEZA de respuesta_total antes de normalizar
        # ---------------------------------------------------------
        import re
        lineas = respuesta_total.strip().split("\n")
        filtrado = []
        encabezado_usado = False
        for linea in lineas:
            # Detectar encabezado
            if "ID" in linea and "Material" in linea and "|" in linea:
                if not encabezado_usado:
                    filtrado.append(linea)
                    encabezado_usado = True
                continue
            # Saltar alineadores Markdown
            if re.fullmatch(r"[:\-\s\|]+", linea):
                continue
            # Saltar líneas muy cortas o basura
            if len(linea.strip()) < 10 or re.fullmatch(r"[a-zA-Z0-9\$\-_]{1,6}", linea.strip()):
                continue
            filtrado.append(linea)

        respuesta_total = "\n".join(filtrado)
        st.markdown(respuesta_total)
        st.session_state["tabla_original"] = respuesta_total

        # Prompt para normalizar
        prompt_normalizar = f"""
Tengo esta tabla con huellas de carbono por elemento IFC:
{respuesta_total}

Tu tarea es:
1. Detectar la columna que representa el GlobalId del objeto IFC. El GlobalId es un identificador único para cada elemento IFC.
   Los GlobalIds suelen tener este formato: '21A42309sirTLSBGWZ' o '3X6TOJOtwNzk'.
   Busca nombres de columna como 'GlobalId', 'GUID', 'IfcGuid' o cualquier otra columna que contenga cadenas similares.
2. Detectar la columna que representa la huella total por elemento.
3. Detectar la unidad a partir del encabezado (por ejemplo, "[kg CO₂ eq]") y aplicar esa unidad a todos los valores.
4. Genera una tabla nueva con estos encabezados exactos:
- ID (GlobalId del elemento IFC)
- Total
- Unidad

⚠️ Muy importante:
- No repitas encabezados si ya aparecieron antes.
- La tabla debe tener solo una línea de encabezados al inicio.
- Devuélvelo estrictamente en formato Markdown de tabla.
- No incluyas explicaciones ni texto adicional.
- No agregues líneas separadoras adicionales.
"""

        with st.spinner(" Normalizando tabla para exportación IFC..."):
            tabla_normalizada = modelo.generate_content(prompt_normalizar).text
            st.text(tabla_normalizada)

            try:
                df_normalizado = pd.read_table(BytesIO(tabla_normalizada.encode()), sep="|", engine="python")
                df_normalizado = df_normalizado.dropna(axis=1, how="all").iloc[1:-1].copy()
                df_normalizado.columns = [col.strip() for col in df_normalizado.columns]
                df_normalizado = df_normalizado.fillna(0)

                col_total = next((c for c in df_normalizado.columns if "total" in c.lower() and "gwp" in c.lower()), None)
                if col_total and col_total != "Total":
                    df_normalizado = df_normalizado.rename(columns={col_total: "Total"})

                st.text(f"Columnas de df_normalizado: {df_normalizado.columns.tolist()}")
                st.session_state["df_resultado"] = df_normalizado

            except Exception as e:
                st.error(f"❌ No se pudo leer la tabla normalizada: {e}")
                st.text(tabla_normalizada)
                st.stop()



# ===============================================================
# 10 --- EXPORTACIÓN IFC CON RESULTADOS -------------------------
# ===============================================================
if "tabla_original" in st.session_state and "ruta_guardado" in st.session_state:
    st.markdown("## \U0001F4C4 Exportar huella de carbono al IFC")

    # Mostrar la tabla original de forma visual clara
    tabla_origen = st.session_state["tabla_original"]
    if isinstance(tabla_origen, str):
        try:
            from io import StringIO
            tabla_io = StringIO(tabla_origen)
            df_origen = pd.read_csv(tabla_io, sep="|", engine="python", skipinitialspace=True)
            df_origen = df_origen.dropna(axis=1, how="all").dropna(axis=0, how="all")
            st.session_state["tabla_original"] = df_origen
        except Exception as e:
            st.warning(f"No se pudo convertir tabla a DataFrame: {e}")
            df_origen = tabla_origen
    else:
        df_origen = tabla_origen

    st.markdown("### \U0001F4DC Vista previa de tabla original")
    if isinstance(df_origen, pd.DataFrame):
        st.dataframe(df_origen)
    else:
        st.text(str(df_origen))

    modelo = cargar_modelo()
    prompt_normalizar = f"""
Tengo esta tabla con huellas de carbono por elemento IFC:
{df_origen.to_markdown(index=False) if isinstance(df_origen, pd.DataFrame) else df_origen}

Tu tarea es:
1. Detectar la columna que representa el GlobalId del objeto IFC.
2. Detectar la columna que representa la huella total por elemento.
3. Detectar la unidad a partir del encabezado (ej: [kg CO₂ eq]) y aplicarla a todos los valores.
4. Devuelve solo la tabla con estos encabezados:
- ID
- Total
- Unidad

Devuélvelo estrictamente en formato Markdown de tabla con estos encabezados exactos: ID | Total | Unidad
Sin texto adicional ni explicaciones. No agregues líneas de separación redundantes ni encabezados repetidos.
"""

    raw_output = modelo.generate_content(prompt_normalizar)
    tabla_normalizada = raw_output.text if hasattr(raw_output, 'text') else str(raw_output)

    st.markdown("### \U0001F4DC Vista previa de tabla entregada por la IA")
    st.markdown(tabla_normalizada)

    try:
        import re
        import csv
        from io import StringIO
        from collections import Counter

        lines = tabla_normalizada.strip().split("\n")
        header_idx = next((i for i, l in enumerate(lines) if '|' in l and 'id' in l.lower() and 'total' in l.lower()), None)
        if header_idx is None:
            raise ValueError("Encabezado de la tabla no encontrado")

        lines = lines[header_idx:]
        table_lines = [line for line in lines if line.count('|') >= 2 and not re.fullmatch(r'\|[-:\s]*\|?', line)]

        raw_header = [h.strip().lower().replace(" ", "_").replace("[", "").replace("]", "") for h in table_lines[0].split('|') if h.strip()]
        counter = Counter()
        header = []
        for col in raw_header[:]:
            count = counter[col]
            if count > 0:
                header.append(f"{col}_{count}")
            else:
                header.append(col)
            counter[col] += 1

        data = []
        for row in table_lines[1:]:
            parsed = list(csv.reader([re.sub(r"\s+", " ", row)], delimiter='|'))[0]
            cleaned = [cell.strip() for cell in parsed]
            # Aceptamos también filas incompletas si contienen al menos ID y Total
            if len(cleaned) >= 2:
                while len(cleaned) < len(header):
                    cleaned.append("")
                data.append(cleaned[:len(header)])

        df_normalizado = pd.DataFrame(data, columns=header)
        df_normalizado.columns = [col.strip() for col in df_normalizado.columns]

        df_normalizado = df_normalizado[~df_normalizado.apply(
            lambda row: all(re.fullmatch(r"[:\-\s]*", str(cell)) for cell in row), axis=1)]

        rename_dict = {}
        for col in df_normalizado.columns:
            col_l = col.lower()
            if 'id' in col_l and "unidad" not in col_l:
                rename_dict[col] = "ID"
            elif 'total' in col_l:
                rename_dict[col] = "Total"
            elif 'unidad' in col_l:
                rename_dict[col] = "Unidad"
        df_normalizado.rename(columns=rename_dict, inplace=True)

        columnas_requeridas = {"ID", "Total"}
        faltantes = columnas_requeridas - set(df_normalizado.columns)
        if faltantes:
            st.error(f"❌ No se pueden exportar resultados al IFC. Faltan columnas: {faltantes}")
            st.stop()

        df_normalizado["ID"] = df_normalizado["ID"].astype(str).apply(lambda x: x.strip())

        def limpiar_valor_total(valor):
            match = re.search(r"[\-\d\.,]+", str(valor))
            if match:
                valor_numerico = match.group(0).replace(",", "")
                try:
                    return float(valor_numerico)
                except ValueError:
                    return 0.0
            return 0.0

        df_normalizado["Total"] = df_normalizado["Total"].apply(limpiar_valor_total)

        if "Unidad" not in df_normalizado.columns:
            df_normalizado["Unidad"] = "kg CO₂ eq"
        else:
            df_normalizado["Unidad"] = df_normalizado["Unidad"].fillna("kg CO₂ eq")

        df_normalizado = df_normalizado[df_normalizado["ID"] != ""].drop_duplicates(subset="ID")

        # ✅ Mostrar tabla en modo visual
        st.markdown("### \U0001F5C3 Vista previa en tabla formateada")
        st.dataframe(df_normalizado)

        # ✅ Comprobación de diferencia con la tabla original
        if isinstance(df_origen, pd.DataFrame):
            ids_origen = set(df_origen.iloc[:, 0].astype(str).str.strip())
            ids_normalizados = set(df_normalizado["ID"])
            ids_faltantes = ids_origen - ids_normalizados
            st.info(f"🔍 Elementos originales: {len(ids_origen)} — Procesados por IA: {len(ids_normalizados)}")
            if ids_faltantes:
                st.warning(f"⚠️ {len(ids_faltantes)} elementos no fueron incluidos en el resultado. Puedes revisarlos manualmente si es necesario.")
                st.text("IDs faltantes:\n" + "\n".join(sorted(ids_faltantes)))

        st.session_state["df_resultado"] = df_normalizado
        st.success("✅ Datos listos para exportar")

    except Exception as e:
        st.error(f"❌ Error al procesar la tabla normalizada: {e}")
        st.text(str(tabla_normalizada))




# ===============================================================
# 11 --- VALIDACIÓN Y EXPORTACIÓN MANUAL ------------------------
# ===============================================================
if "df_resultado" in st.session_state and "ruta_guardado" in st.session_state:
    st.markdown("## 🛠️ Exportar huella de carbono al IFC")
    df = st.session_state["df_resultado"].copy()
    df.columns = [col.strip() for col in df.columns]

    # Limpiar columna ID y omitir valores inválidos
    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(str).apply(lambda x: x.strip())
        df = df[~df["ID"].isin(["", "None", "none", "-", "--", "------------------------"])]
        df = df[~df["ID"].str.match(r"^-+$")]  # Filtra IDs compuestos solo por guiones
    else:
        st.error("❌ La columna 'ID' no está presente.")
        st.stop()

    # Limpiar columna Total
    if "Total" in df.columns:
        def limpiar_valor_total(valor):
            import re
            match = re.search(r"[\-\d\.,]+", str(valor))
            if match:
                valor_numerico = match.group(0).replace(",", "")
                try:
                    return float(valor_numerico)
                except ValueError:
                    return 0.0
            return 0.0

        df["Total"] = df["Total"].apply(limpiar_valor_total)
    else:
        st.error("❌ La columna 'Total' no está presente.")
        st.stop()

    # Unidad por defecto
    if "Unidad" not in df.columns:
        df["Unidad"] = "kg CO₂ eq"
    else:
        df["Unidad"] = df["Unidad"].fillna("kg CO₂ eq")

    # Eliminar duplicados
    df = df.drop_duplicates(subset="ID")

    st.markdown("### ✅ Datos listos para exportar")
    st.dataframe(df)

    import ifcopenshell
    model_debug = ifcopenshell.open(st.session_state["ruta_guardado"])
    no_encontrados = []

    for guid in df["ID"]:
        guid = str(guid).strip()
        try:
            if not model_debug.by_guid(guid):
                no_encontrados.append(guid)
        except Exception as e:
            st.warning(f"⚠️ Error al buscar GUID '{guid}': {e}")
            no_encontrados.append(guid)

    if no_encontrados:
        st.warning(f"⚠️ Algunos GUIDs no se encontraron en el IFC:\n{no_encontrados}")
    else:
        st.success("✅ Todos los GUIDs están presentes en el archivo IFC")

    if st.button("🚀 Ejecutar exportación IFC"):
        try:
            ruta_exportado = agregar_huella_ifc(
                ruta_ifc_original=st.session_state["ruta_guardado"],
                df_resultado=df,
                nombre_salida="IFC_con_ImpactoAmbiental.ifc"
            )
            st.session_state["ifc_exportado"] = ruta_exportado
            st.success("✅ IFC exportado correctamente.")
        except Exception as e:
            st.error(f"❌ Error al exportar: {e}")

    if "ifc_exportado" in st.session_state:
        with open(st.session_state["ifc_exportado"], "rb") as f:
            st.download_button("⬇️ Descargar IFC exportado", data=f.read(), file_name=os.path.basename(st.session_state["ifc_exportado"]), mime="application/octet-stream")
# ===============================================================
# 12 --- ASISTENTE EXPERTO EN SOSTENIBILIDAD --------------------
# ===============================================================

st.markdown("## 🧠 Consultas sobre sostenibilidad y huella de carbono")

if "hojas_sostenibilidad" in st.session_state and "df_resultado" in st.session_state:
    df_resultado = st.session_state["df_resultado"].copy()
    hojas_sostenibilidad = st.session_state["hojas_sostenibilidad"]

    # Inicializar historial si no existe
    if "historial_chat" not in st.session_state:
        st.session_state["historial_chat"] = []

    # Entrada tipo chat
    consulta_usuario = st.chat_input("Haz una pregunta sobre los cálculos de huella de carbono...")

    if consulta_usuario:
        modelo = cargar_modelo()
        contexto_ifc = df_resultado.to_markdown(index=False)
        contexto_bbdd = formatear_hojas_para_ia(hojas_sostenibilidad, max_filas_por_hoja=20)

        # Construir historial como parte del prompt (últimos 5 turnos)
        historial = st.session_state["historial_chat"][-5:]
        historial_prompt = "\n\n".join([
            f"Usuario: {q}\nAsistente: {r}" for q, r in historial
        ])

        prompt_final = f"""
Actúa como un experto en sostenibilidad ambiental y análisis de huella de carbono.
Responde únicamente sobre los datos proporcionados del modelo IFC y la base de datos de sostenibilidad.

### Historial de la conversación:
{historial_prompt}

### Nueva pregunta:
Usuario: {consulta_usuario}

### Datos del modelo IFC:
{contexto_ifc}

### Base de datos de sostenibilidad:
{contexto_bbdd}

Asistente:"""

        with st.spinner("Consultando al asistente de sostenibilidad..."):
            respuesta = modelo.generate_content(prompt_final).text

        # Guardar nueva interacción en el historial
        st.session_state["historial_chat"].append((consulta_usuario, respuesta))

    # Mostrar historial completo como conversación
    for idx, (pregunta, respuesta) in enumerate(st.session_state["historial_chat"][-5:]):
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            st.markdown(respuesta)
else:
    st.info("🔄 Carga un archivo IFC y realiza los cálculos para activar el asistente.")
