import os
import pandas as pd

from database.datasets_db import save_dataset
from database.neo4j import neo4j_connection


def _limpiar_texto(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.lower() == "nan":
        return ""

    return texto


def _es_numero(valor):
    if pd.isna(valor):
        return False

    try:
        float(valor)
        return True
    except (ValueError, TypeError):
        return False


def _detectar_columnas_cmf(df, fila_header):
    """
    Detecta automáticamente las columnas que representan CMF.

    En el archivo actual encontramos:

        CMF 1-10  -> columnas 1-10
        CMF 11-20 -> columnas 12-21
        CMF 21-31 -> columnas 23-33

    La función no depende de esas posiciones:
    lee los encabezados y toma únicamente los encabezados
    numéricos que representan CMF.
    """

    cmf_columnas = {}

    for col_idx in range(1, df.shape[1]):
        valor = df.iloc[fila_header, col_idx]

        if not _es_numero(valor):
            continue

        numero = int(float(valor))

        # Solo consideramos CMF del 1 al 31.
        if 1 <= numero <= 31:
            cmf_columnas[col_idx] = f"CMF {numero}"

    return cmf_columnas


def _detectar_columnas_ttl(df, fila_header):
    """
    Detecta las columnas TTL del bloque.

    El Excel actual tiene TTL en:
        - TTL después de CMF 1-10
        - TTL después de CMF 11-20
        - TTL después de CMF 21-31
        - TTL / GRAL como total general
    """

    ttl_columnas = []

    for col_idx in range(df.shape[1]):
        valor = _limpiar_texto(df.iloc[fila_header, col_idx]).upper()

        if valor == "TTL":
            ttl_columnas.append(col_idx)

    return ttl_columnas


def _extraer_valor_seguro(df, fila, columna):
    """
    Extrae un valor numérico sin intentar convertir encabezados
    o textos arbitrarios a float.
    """

    valor = df.iloc[fila, columna]

    if pd.isna(valor):
        return None

    if isinstance(valor, str):
        valor = valor.strip()

        if not valor:
            return None

        # Si accidentalmente encontramos un encabezado,
        # simplemente no lo tratamos como dato.
        if valor.upper() in {
            "TTL",
            "TTL / GRAL",
            "TERR",
            "CONCEPTOS"
        }:
            return None

    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def _buscar_polyclinico(df, fila_actual, policlinico_actual):
    """
    Busca si una fila contiene el nombre del policlínico.
    """

    texto = _limpiar_texto(df.iloc[fila_actual, 0])

    if texto.upper().startswith("POL."):
        return texto

    return policlinico_actual


def parse_and_insert_consolidado(file_path, documento_nombre=None):
    try:
        # ---------------------------------------------------------
        # 1. Leer Excel
        # ---------------------------------------------------------

        df = pd.read_excel(
            file_path,
            header=None,
            engine="xlrd"
        )

        if df.empty:
            print("El Excel está vacío.")
            return False

        print(
            f"Excel leído correctamente: "
            f"{df.shape[0]} filas x {df.shape[1]} columnas"
        )

        # ---------------------------------------------------------
        # 2. Detectar todos los bloques CONCEPTOS
        # ---------------------------------------------------------

        bloques = []

        for fila in range(len(df)):
            valor = _limpiar_texto(df.iloc[fila, 0]).upper()

            if valor == "CONCEPTOS":
                bloques.append(fila)

        if not bloques:
            print("No se encontró ninguna fila 'CONCEPTOS'.")
            return False

        print(f"Bloques CONCEPTOS encontrados: {len(bloques)}")

        # ---------------------------------------------------------
        # 3. Policlinico
        # ---------------------------------------------------------

        policlinico = ""

        for fila in range(bloques[0], -1, -1):
            texto = _limpiar_texto(df.iloc[fila, 0])

            if texto.upper().startswith("POL."):
                policlinico = texto
                break

        if not policlinico:
            policlinico = "Policlínico no identificado"

        print(f"Policlínico detectado: {policlinico}")

        # ---------------------------------------------------------
        # 4. Procesar bloques
        # ---------------------------------------------------------

        conceptos = []

        for indice_bloque, fila_header in enumerate(bloques):

            # Actualizar policlínico si existe uno nuevo antes del bloque.
            for fila_busqueda in range(fila_header, -1, -1):
                texto = _limpiar_texto(df.iloc[fila_busqueda, 0])

                if texto.upper().startswith("POL."):
                    policlinico = texto
                    break

            # Detectar CMF de este bloque.
            cmf_columnas = _detectar_columnas_cmf(
                df,
                fila_header
            )

            ttl_columnas = _detectar_columnas_ttl(
                df,
                fila_header
            )

            print(
                f"Bloque {indice_bloque + 1}: "
                f"fila {fila_header}, "
                f"CMF detectados: {len(cmf_columnas)}, "
                f"TTL: {ttl_columnas}"
            )

            # -----------------------------------------------------
            # Determinar dónde termina el bloque
            # -----------------------------------------------------

            if indice_bloque + 1 < len(bloques):
                fila_fin = bloques[indice_bloque + 1]
            else:
                fila_fin = len(df)

            # -----------------------------------------------------
            # Procesar filas del bloque
            # -----------------------------------------------------

            for fila in range(fila_header + 1, fila_fin):

                nombre = _limpiar_texto(df.iloc[fila, 0])

                if not nombre:
                    continue

                # Evitar filas administrativas que puedan aparecer
                # dentro del bloque.
                nombre_upper = nombre.upper()

                if nombre_upper.startswith("POL."):
                    continue

                if nombre_upper in {
                    "DR:",
                    "CONCEPTOS"
                }:
                    continue

                registros = {}

                # -------------------------------------------------
                # Extraer CMF
                # -------------------------------------------------

                for col_idx, cmf_nombre in cmf_columnas.items():

                    valor = _extraer_valor_seguro(
                        df,
                        fila,
                        col_idx
                    )

                    if valor is not None:
                        registros[cmf_nombre] = valor

                # -------------------------------------------------
                # Extraer TTL / total general
                # -------------------------------------------------

                total_general = None

                # Preferimos TTL / GRAL.
                for col_idx in range(df.shape[1]):
                    encabezado = _limpiar_texto(
                        df.iloc[fila_header, col_idx]
                    ).upper()

                    if encabezado == "TTL / GRAL":
                        total_general = _extraer_valor_seguro(
                            df,
                            fila,
                            col_idx
                        )
                        break

                # Si no existe TTL / GRAL, usamos el último TTL.
                if total_general is None and ttl_columnas:
                    total_general = _extraer_valor_seguro(
                        df,
                        fila,
                        ttl_columnas[-1]
                    )

                # -------------------------------------------------
                # Guardar concepto
                # -------------------------------------------------

                conceptos.append({
                    "nombre": nombre,
                    "total_general": total_general,
                    "registros": registros,
                    "tipo": "Concepto"
                })

        # ---------------------------------------------------------
        # 5. Comprobar que obtuvimos datos
        # ---------------------------------------------------------

        if not conceptos:
            print("No se pudieron extraer conceptos del Excel.")
            return False

        # Obtener todos los CMF realmente encontrados.
        cmfs_encontrados = set()

        for concepto in conceptos:
            cmfs_encontrados.update(
                concepto.get("registros", {}).keys()
            )

        cmfs = sorted(
            cmfs_encontrados,
            key=lambda x: int(x.split()[-1])
        )

        print(
            f"Conceptos extraídos: {len(conceptos)}"
        )

        print(
            f"CMF encontrados: {len(cmfs)} -> {cmfs}"
        )

        # ---------------------------------------------------------
        # 6. Crear documento
        # ---------------------------------------------------------

        doc = {
            "filename": (
                documento_nombre
                or os.path.basename(file_path)
            ),
            "policlinico": policlinico,
            "cmfs": cmfs,
            "conceptos": conceptos,
        }

        # ---------------------------------------------------------
        # 7. Guardar MongoDB
        # ---------------------------------------------------------

        save_dataset(doc)

        print("Dataset guardado correctamente en MongoDB.")

        # ---------------------------------------------------------
        # 8. Guardar Neo4j
        # ---------------------------------------------------------

        neo4j_connection.insert_medical_graph(
            policlinico=doc["policlinico"],
            cmfs=doc["cmfs"],
            conceptos=doc["conceptos"],
            filename=doc["filename"]
        )

        print("Grafo médico guardado correctamente en Neo4j.")

        return True

    except Exception as e:
        import traceback

        print("========== ERROR PARSEANDO EXCEL ==========")
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje: {e}")
        traceback.print_exc()
        print("===========================================")

        return False
