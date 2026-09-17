import os
from neo4j import GraphDatabase


class Neo4jConnection:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")

        if not self.uri:
            raise ValueError("NEO4J_URI no está configurado")

        if not self.username:
            raise ValueError("NEO4J_USERNAME no está configurado")

        if not self.password:
            raise ValueError("NEO4J_PASSWORD no está configurado")

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )

    def verify_connection(self):
        self.driver.verify_connectivity()
        return True

    def execute_query(self, query, parameters=None):
        result = self.driver.execute_query(
            query,
            parameters or {},
            database_=self.database
        )

        return result
    def insert_medical_graph(self, policlinico, cmfs, conceptos, filename=None):
        queries_executed = 0

    # 1. Crear policlínico
    self.execute_query(
        """
        MERGE (p:Policlinico {nombre: $nombre})
        """,
        {"nombre": policlinico}
    )
    queries_executed += 1

    # 2. Crear CMF y relacionarlo con el policlínico
    for cmf in cmfs:
        cmf_nombre = cmf.get("nombre")

        self.execute_query(
            """
            MERGE (c:CMF {
                nombre: $nombre,
                policlinico: $policlinico
            })

            WITH c
            MATCH (p:Policlinico {nombre: $policlinico})

            MERGE (c)-[:PERTENECE_A]->(p)
            """,
            {
                "nombre": cmf_nombre,
                "policlinico": policlinico
            }
        )
        queries_executed += 1

    # 3. Crear conceptos y registros
    for concepto in conceptos:
        concepto_nombre = concepto.get("nombre")
        total_general = concepto.get("total_general", 0)
        tipo = concepto.get("tipo", "concepto")

        # Concepto principal
        self.execute_query(
            """
            MERGE (con:Concepto {nombre: $nombre})
            SET con.total_general = $total_general,
                con.tipo = $tipo
            """,
            {
                "nombre": concepto_nombre,
                "total_general": total_general,
                "tipo": tipo
            }
        )
        queries_executed += 1

        # Registros asociados a cada CMF
        for registro in concepto.get("registros", []):
            cmf_nombre = registro.get("cmf")
            valor = registro.get("valor", 0)

            self.execute_query(
                """
                MATCH (c:CMF {
                    nombre: $cmf,
                    policlinico: $policlinico
                })

                MATCH (con:Concepto {
                    nombre: $concepto
                })

                CREATE (r:Registro {
                    valor: $valor
                })

                MERGE (r)-[:REGISTRADO_EN]->(c)
                MERGE (r)-[:CORRESPONDE_A]->(con)
                """,
                {
                    "cmf": cmf_nombre,
                    "policlinico": policlinico,
                    "concepto": concepto_nombre,
                    "valor": valor
                }
            )
            queries_executed += 1

    # 4. Documento de origen
    if filename:
        self.execute_query(
            """
            MERGE (d:Documento {nombre: $nombre})
            """,
            {"nombre": filename}
        )

        self.execute_query(
            """
            MATCH (d:Documento {nombre: $documento})
            MATCH (p:Policlinico {nombre: $policlinico})
            MERGE (d)-[:CORRESPONDE_A]->(p)
            """,
            {
                "documento": filename,
                "policlinico": policlinico
            }
        )

        queries_executed += 2

        return queries_executed
    
    def close(self):
        self.driver.close()


neo4j_connection = Neo4jConnection()
