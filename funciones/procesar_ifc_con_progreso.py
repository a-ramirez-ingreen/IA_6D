
import re
import ifcopenshell
import pandas as pd
import os

def es_valor_valido(valor):
    if not valor:
        return False
    valor_str = str(valor).strip().lower()
    return valor_str not in ["n/a", "na", "none", "empty", "-", "sin definir", ""]

def procesar_ifc(ruta_ifc, carpeta_salida="resultados", update_progress=None):
    if not os.path.isfile(ruta_ifc):
        raise FileNotFoundError(f"Archivo IFC no encontrado: {ruta_ifc}")

    os.makedirs(carpeta_salida, exist_ok=True)
    model = ifcopenshell.open(ruta_ifc)
    ifc_filename = os.path.splitext(os.path.basename(ruta_ifc))[0]

    data = []
    productos = model.by_type("IfcProduct")
    total = len(productos)

    for idx, element in enumerate(productos):
        if update_progress:
            update_progress(idx / total)

        element_data = {
            "ID": element.GlobalId,
            "Nombre": getattr(element, "Name", "N/A"),
        }

        # Propiedades Pset
        props = {}
        for rel in model.by_type("IfcRelDefinesByProperties"):
            if rel.RelatedObjects and element in rel.RelatedObjects:
                prop_def = rel.RelatingPropertyDefinition
                if prop_def.is_a("IfcPropertySet"):
                    for prop in prop_def.HasProperties:
                        value = getattr(prop, "NominalValue", None)
                        if hasattr(value, "wrappedValue"):
                            value = value.wrappedValue
                        props[f"{prop_def.Name}_{prop.Name}"] = value

        # Materiales
        materiales = set()
        for rel in model.by_type("IfcRelAssociatesMaterial"):
            if rel.RelatedObjects and element in rel.RelatedObjects:
                mat = rel.RelatingMaterial
                posibles = []
                if hasattr(mat, "Name"):
                    posibles.append(mat.Name)
                if hasattr(mat, "ForLayerSet"):
                    for layer in mat.ForLayerSet.MaterialLayers:
                        if hasattr(layer.Material, "Name"):
                            posibles.append(layer.Material.Name)
                for nombre in posibles:
                    if es_valor_valido(nombre):
                        materiales.add(nombre.strip())

        # Atributos simples
        for attr in dir(element):
            if not attr.startswith("_") and not callable(getattr(element, attr, None)):
                val = getattr(element, attr)
                if isinstance(val, (str, int, float, bool)):
                    element_data[attr] = val

        # Cantidades (IFC4)
        quantities = {}
        if model.schema == "IFC4":
            for rel in model.by_type("IfcRelDefinesByQuantity"):
                if rel.RelatedObjects and element in rel.RelatedObjects:
                    for q in rel.RelatingQuantity.Quantities:
                        val = getattr(q, "VolumeValue", getattr(q, "AreaValue", getattr(q, "LengthValue", None)))
                        if hasattr(val, "wrappedValue"):
                            val = val.wrappedValue
                        if val is not None:
                            quantities[q.Name] = val

        final_data = {
            **element_data,
            **props,
            "Material_IFC": ", ".join(materiales) if materiales else "N/A",
            **quantities
        }

        data.append(final_data)

    df = pd.DataFrame(data)
    output_path = os.path.join(carpeta_salida, f"{ifc_filename}.csv")
    df.to_csv(output_path, index=False)

    return df
