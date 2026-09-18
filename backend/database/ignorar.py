import re

from database.neo4j_queries import (
    get_all_medical_data,
    search_by_cmf,
    search_by_concept,
)


def extract_cmf(question):
    """
    Detecta expresiones como:
    CMF 1
    CMF 2
    consultorio 3
    consultorio médico 4
    """

    pattern = r"(?:cmf|consultorio(?:\s+m[eé]dico)?)\s*(\d+)"

    match = re.search(
        pattern,
        question,
        re.IGNORECASE
    )

    if match:
        return f"CMF {match.group(1)}"

    return None


def extract_concept(question):
    """
    Extrae de forma sencilla el concepto médico
    buscando palabras relevantes conocidas.
    """

    conceptos = [
        "hipertensión",
        "hipertension",
        "diabetes",
        "asma",
        "embarazo",
        "mortalidad",
        "natalidad",
        "enfermedades",
        "consultas",
        "pacientes",
        "vacunación",
        "vacunacion",
    ]

    question_lower = question.lower()

    for concepto in conceptos:
        if concepto in question_lower:
            return concepto

    return None


def select_medical_data(question):
    """
    Decide qué información consultar en Neo4j
    según la pregunta del usuario.
    """

    cmf = extract_cmf(question)
    concepto = extract_concept(question)

    # Caso 1: CMF + concepto
    if cmf and concepto:
        data = search_by_cmf(cmf)

        filtered_data = [
            item
            for item in data
            if concepto.lower() in item["concepto"].lower()
        ]

        return {
            "cmf": cmf,
            "concepto": concepto,
            "data": filtered_data,
        }

    # Caso 2: solo CMF
    if cmf:
        return {
            "cmf": cmf,
            "concepto": None,
            "data": search_by_cmf(cmf),
        }

    # Caso 3: solo concepto
    if concepto:
        return {
            "cmf": None,
            "concepto": concepto,
            "data": search_by_concept(concepto),
        }

    # Caso 4: no se detectaron parámetros
    return {
        "cmf": None,
        "concepto": None,
        "data": get_all_medical_data(limit=50),
    }
