from database.neo4j import neo4j_connection


def create_constraints():
    queries = [
        """
        CREATE CONSTRAINT policlinico_nombre IF NOT EXISTS
        FOR (p:Policlinico)
        REQUIRE p.nombre IS UNIQUE
        """,

        """
        CREATE CONSTRAINT cmf_nombre IF NOT EXISTS
        FOR (c:CMF)
        REQUIRE c.nombre IS UNIQUE
        """,

        """
        CREATE CONSTRAINT concepto_nombre IF NOT EXISTS
        FOR (c:Concepto)
        REQUIRE c.nombre IS UNIQUE
        """,

        """
        CREATE CONSTRAINT subconcepto_nombre IF NOT EXISTS
        FOR (s:Subconcepto)
        REQUIRE s.nombre IS UNIQUE
        """,

        """
        CREATE CONSTRAINT documento_nombre IF NOT EXISTS
        FOR (d:Documento)
        REQUIRE d.nombre IS UNIQUE
        """
    ]

    for query in queries:
        neo4j_connection.execute_query(query)

    return True
