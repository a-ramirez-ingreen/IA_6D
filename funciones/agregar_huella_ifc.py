import os
import pandas as pd
import ifcopenshell
import ifcopenshell.api

def aplicar_colores_por_impacto(model, df_resultado):
    """Asigna colores a los elementos del IFC según su huella de carbono (compatible con visores como BIMvision)."""
    if "ID" not in df_resultado.columns or "Total" not in df_resultado.columns:
        raise ValueError("❌ El DataFrame necesita columnas 'ID' y 'Total'")

    df_resultado["Total"] = pd.to_numeric(df_resultado["Total"], errors="coerce").fillna(0.0)

    min_val = df_resultado["Total"].min()
    max_val = df_resultado["Total"].max()
    rango = max_val - min_val if max_val != min_val else 1e-6

    color_cache = {}

    def interpolar_color(valor):
        norm = (valor - min_val) / rango
        if norm < 0.5:
            r = int(2 * norm * 255)
            g = 255
        else:
            r = 255
            g = int((1 - 2 * (norm - 0.5)) * 255)
        b = 0
        return (r / 255.0, g / 255.0, b / 255.0)

    for _, row in df_resultado.iterrows():
        guid = str(row["ID"]).strip()
        total = row["Total"]
        producto = model.by_guid(guid)
        if not producto or not hasattr(producto, "Representation"):
            continue

        rep = producto.Representation
        if not rep or not hasattr(rep, "Representations"):
            continue

        for subrep in rep.Representations:
            if hasattr(subrep, "Items"):
                for item in subrep.Items:
                    color_rgb = interpolar_color(total)
                    color_key = tuple(round(c, 3) for c in color_rgb)

                    if color_key not in color_cache:
                        color = model.create_entity("IfcColourRgb", Name=None, Red=color_key[0], Green=color_key[1], Blue=color_key[2])
                        surface_style = model.create_entity("IfcSurfaceStyle",
                            Name=f"Color_{color_key}",
                            Side="BOTH",
                            Styles=[model.create_entity("IfcSurfaceStyleRendering", SurfaceColour=color)]
                        )
                        pres_style = model.create_entity("IfcPresentationStyleAssignment", Styles=[surface_style])
                        color_cache[color_key] = pres_style

                    model.create_entity("IfcStyledItem", Item=item, Styles=[color_cache[color_key]])


def agregar_huella_ifc(ruta_ifc_original, df_resultado, nombre_salida="IFC_con_pset_exportado.ifc"):
    if not os.path.isfile(ruta_ifc_original):
        raise FileNotFoundError("❌ IFC original no encontrado")

    if "Total" not in df_resultado.columns:
        raise ValueError("❌ No se encontró columna 'Total' en el DataFrame.")

    if "ID" not in df_resultado.columns:
        raise ValueError("❌ La columna 'ID' es obligatoria para identificar los elementos IFC.")

    model = ifcopenshell.open(ruta_ifc_original)
    errores = []

    for idx, row in df_resultado.iterrows():
        guid = str(row.get("ID")).strip()
        huella = row.get("Total")
        unidad = row.get("Unidad") if "Unidad" in row and pd.notna(row["Unidad"]) else "kg CO2 eq"

        if not guid or pd.isna(huella):
            errores.append(f"Fila {idx}: ID o Total no válidos → ID: {guid}, Total: {huella}")
            continue

        producto = model.by_guid(guid)
        if not producto:
            errores.append(f"⚠️ No se encontró el objeto IFC con GUID: {guid}")
            continue

        try:
            pset = ifcopenshell.api.run("pset.add_pset", model, product=producto, name="ImpactoAmbiental")
            ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={
                "IA_HuellaCarbono": float(huella),
                "IA_Unidad": str(unidad)
            })
        except Exception as e:
            errores.append(f"❌ Error al añadir pset a {guid}: {e}")

    aplicar_colores_por_impacto(model, df_resultado)

    os.makedirs("resultados", exist_ok=True)
    ruta_exportado = os.path.join("resultados", nombre_salida)
    model.write(ruta_exportado)

    if errores:
        with open("resultados/errores_exportacion.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(errores))

    return ruta_exportado
