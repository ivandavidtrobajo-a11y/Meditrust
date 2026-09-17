from database.neo4j import neo4j_connection


def get_all_medical_data(limit=100):
    """
    Obtiene registros médicos del grafo.
    """

    query = """
    MATCH (r:Registro)-[:REGISTRADO_EN]->(cmf:CMF)
    MATCH (r)-[:CORRESPONDE_A]->(con:Concepto)
    MATCH (cmf)-[:PERTENECE_A]->(p:Policlinico)

    RETURN
        p.nombre AS policlinico,
        cmf.nombre AS cmf,
        con.nombre AS concepto,
        con.tipo AS tipo,
        r.valor AS valor

    ORDER BY cmf.nombre, concepto.nombre
    LIMIT $limit
    """

    result = neo4j_connection.execute_query(
        query,
        {"limit": limit}
    )

    return [record.data() for record in result.records]


def search_by_cmf(cmf, limit=100):
    """
    Busca información perteneciente a un CMF específico.
    """

    query = """
    MATCH (r:Registro)-[:REGISTRADO_EN]->(cmf_node:CMF)
    MATCH (r)-[:CORRESPONDE_A]->(con:Concepto)
    MATCH (cmf_node)-[:PERTENECE_A]->(p:Policlinico)

    WHERE toLower(cmf_node.nombre) = toLower($cmf)

    RETURN
        p.nombre AS policlinico,
        cmf_node.nombre AS cmf,
        con.nombre AS concepto,
        con.tipo AS tipo,
        r.valor AS valor

    ORDER BY con.nombre
    LIMIT $limit
    """

    result = neo4j_connection.execute_query(
        query,
        {
            "cmf": cmf,
            "limit": limit
        }
    )

    return [record.data() for record in result.records]


def search_by_concept(concepto, limit=100):
    """
    Busca información relacionada con un concepto.
    """

    query = """
    MATCH (r:Registro)-[:REGISTRADO_EN]->(cmf:CMF)
    MATCH (r)-[:CORRESPONDE_A]->(con:Concepto)
    MATCH (cmf)-[:PERTENECE_A]->(p:Policlinico)

    WHERE toLower(con.nombre) CONTAINS toLower($concepto)

    RETURN
        p.nombre AS policlinico,
        cmf.nombre AS cmf,
        con.nombre AS concepto,
        con.tipo AS tipo,
        r.valor AS valor

    ORDER BY cmf.nombre, con.nombre
    LIMIT $limit
    """

    result = neo4j_connection.execute_query(
        query,
        {
            "concepto": concepto,
            "limit": limit
        }
    )

    return [record.data() for record in result.records]


def get_concept_totals(limit=100):
    """
    Obtiene los totales generales de los conceptos.
    """

    query = """
    MATCH (con:Concepto)

    RETURN
        con.nombre AS concepto,
        con.tipo AS tipo,
        con.total_general AS total_general

    ORDER BY con.nombre
    LIMIT $limit
    """

    result = neo4j_connection.execute_query(
        query,
        {"limit": limit}
    )

    return [record.data() for record in result.records]
