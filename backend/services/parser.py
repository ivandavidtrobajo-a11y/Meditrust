import pandas as pd
from database.datasets_db import save_dataset
from database.mongodb import get_db
from database.neo4j import neo4j_connection


def _detectar_formato_excel(df):
    header_ttl = str(df.iloc[2, 16]).strip().upper() if pd.notna(df.iloc[2, 16]) else ""
    if "TTL" in header_ttl or "GRAL" in header_ttl:
        return {"cmf_cols": range(1, 12), "ttl_col": 16}
    return {"cmf_cols": range(1, 11), "ttl_col": 11}


def _extraer_cmf_nombres(df, formato):
    cmf_nombres = {}
    for i in formato["cmf_cols"]:
        nombre_cmf = str(df.iloc[2, i]).strip()
        if nombre_cmf and nombre_cmf.lower() != 'nan':
            try:
                num = int(float(nombre_cmf))
                nombre_cmf = f"CMF {num}"
            except ValueError:
                pass
            cmf_nombres[i] = nombre_cmf
    return cmf_nombres


def _extraer_valor(df, idx_fila, col_idx):
    valor = df.iloc[idx_fila, col_idx]
    if pd.notna(valor) and str(valor).strip() != "":
        return float(valor)
    return None


def parse_and_insert_consolidado(file_path, documento_nombre=None):
    try:
        df = pd.read_excel(file_path, header=None)
        formato = _detectar_formato_excel(df)
        cmf_nombres = _extraer_cmf_nombres(df, formato)
        cmf_list = list(cmf_nombres.values())
        nombre_pol = str(df.iloc[0, 0]).strip()

        jerarquia = {
            3: [4, 5, 6], 7: [8, 9, 10], 11: [12, 13, 14], 15: [16, 17, 18],
            19: [20, 21, 22], 23: [24, 25, 26], 39: list(range(40, 52)),
            58: [59, 60, 61], 62: [63, 64, 65], 66: [67, 68, 69],
            70: [71, 72, 73], 77: [78, 79, 80], 81: [82, 83, 84],
            85: [86, 87, 88], 91: [92, 93, 94], 95: list(range(96, 101)),
            101: list(range(102, 107)), 109: list(range(110, 115)),
            115: list(range(116, 121)), 121: list(range(122, 127)),
            127: list(range(128, 133)), 143: list(range(144, 151)),
            180: [181, 182, 183], 184: list(range(185, 190)),
            190: list(range(191, 196)), 197: [198, 199, 200]
        }

        solas = (
            list(range(27, 39)) + list(range(52, 56)) + [57] + list(range(74, 77)) +
            [89, 90] + list(range(133, 141)) + [142] + list(range(151, 177)) +
            list(range(202, 211))
        )

        conceptos = []

        def procesar_fila(idx, concepto_padre_nombre=None):
            nombre_crudo = str(df.iloc[idx, 0]).strip()
            if not nombre_crudo or nombre_crudo.lower() == 'nan':
                return None

            if concepto_padre_nombre:
                nombre_final = f"{concepto_padre_nombre} - {nombre_crudo}"
            else:
                nombre_final = nombre_crudo

            registros = {}
            for col_idx in formato["cmf_cols"]:
                valor = _extraer_valor(df, idx, col_idx)
                if valor is not None:
                    registros[cmf_nombres[col_idx]] = valor

            ttl_gral = _extraer_valor(df, idx, formato["ttl_col"])

            conceptos.append({
                "nombre": nombre_final,
                "total_general": ttl_gral,
                "registros": registros,
                "tipo": "Subconcepto" if concepto_padre_nombre else "Concepto",
            })

            return nombre_final

        for idx_padre, idxs_hijos in jerarquia.items():
            nombre_padre = procesar_fila(idx_padre)
            for idx_hijo in idxs_hijos:
                procesar_fila(idx_hijo, nombre_padre)

        for idx_sola in solas:
            procesar_fila(idx_sola)

        doc = {
            "filename": documento_nombre or file_path.split("/")[-1],
            "policlinico": nombre_pol,
            "cmfs": cmf_list,
            "conceptos": conceptos,
        }

        save_dataset(doc)
        neo4j_connection.insert_medical_graph(
            policlinico=doc["policlinico"],
            cmfs=doc["cmfs"],
            conceptos=doc["conceptos"],
            filename=doc["filename"]
        )
        return True

    except Exception as e:
           import traceback

           print("========== ERROR PARSEANDO EXCEL ==========")
           print(f"Tipo de error: {type(e).__name__}")
           print(f"Mensaje: {e}")
           traceback.print_exc()
           print("===========================================")

           return False
