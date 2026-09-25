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
    def insert_medical_graph(
        self,
        policlinico,
        cmfs,
        conceptos,
        filename=None
    ):
        """
        Inserta el dataset médico en Neo4j.
    
        Estructura:
    
        Policlínico
            |
            └── CMF
                  |
                  └── Registro
                        |
                        └── Concepto
        """
    
        # ---------------------------------------------------------
        # 1. Policlínico
        # ---------------------------------------------------------
    
        self.execute_query(
            """
            MERGE (p:Policlinico {nombre: $policlinico})
            """,
            {
                "policlinico": policlinico
            }
        )
    
        # ---------------------------------------------------------
        # 2. Documento
        # ---------------------------------------------------------
    
        if filename:
            self.execute_query(
                """
                MERGE (d:Documento {nombre: $filename})
                SET d.policlinico = $policlinico
                """,
                {
                    "filename": filename,
                    "policlinico": policlinico
                }
            )
    
            self.execute_query(
                """
                MATCH (d:Documento {nombre: $filename})
                MATCH (p:Policlinico {nombre: $policlinico})
                MERGE (d)-[:PERTENECE_A]->(p)
                """,
                {
                    "filename": filename,
                    "policlinico": policlinico
                }
            )
    
        # ---------------------------------------------------------
        # 3. CMF
        # ---------------------------------------------------------
    
        for cmf in cmfs:
    
            # Nuestro parser actual produce strings:
            # "CMF 1", "CMF 2", etc.
            if isinstance(cmf, dict):
                cmf_nombre = cmf.get("nombre")
            else:
                cmf_nombre = str(cmf).strip()
    
            if not cmf_nombre:
                continue
    
            self.execute_query(
                """
                MERGE (c:CMF {
                    nombre: $cmf_nombre,
                    policlinico: $policlinico
                })
    
                WITH c
    
                MATCH (p:Policlinico {
                    nombre: $policlinico
                })
    
                MERGE (c)-[:PERTENECE_A]->(p)
                """,
                {
                    "cmf_nombre": cmf_nombre,
                    "policlinico": policlinico
                }
            )
    
        # ---------------------------------------------------------
        # 4. Conceptos y registros
        # ---------------------------------------------------------
    
        for concepto in conceptos:
    
            nombre = concepto.get("nombre")
    
            if not nombre:
                continue
    
            total_general = concepto.get("total_general")
            tipo = concepto.get("tipo", "Concepto")
    
            # -----------------------------------------------------
            # Crear concepto
            # -----------------------------------------------------
    
            self.execute_query(
                """
                MERGE (con:Concepto {
                    nombre: $nombre,
                    policlinico: $policlinico
                })
    
                SET con.total_general = $total_general,
                    con.tipo = $tipo
                """,
                {
                    "nombre": nombre,
                    "policlinico": policlinico,
                    "total_general": total_general,
                    "tipo": tipo
                }
            )
    
            # -----------------------------------------------------
            # Documento -> Concepto
            # -----------------------------------------------------
    
            if filename:
                self.execute_query(
                    """
                    MATCH (d:Documento {nombre: $filename})
                    MATCH (con:Concepto {
                        nombre: $nombre,
                        policlinico: $policlinico
                    })
    
                    MERGE (d)-[:CONTIENE]->(con)
                    """,
                    {
                        "filename": filename,
                        "nombre": nombre,
                        "policlinico": policlinico
                    }
                )
    
            # -----------------------------------------------------
            # Registros CMF
            # -----------------------------------------------------
    
            registros = concepto.get("registros", {})
    
            for cmf_nombre, valor in registros.items():
    
                if valor is None:
                    continue
    
                self.execute_query(
                    """
                    MATCH (c:CMF {
                        nombre: $cmf_nombre,
                        policlinico: $policlinico
                    })
    
                    MATCH (con:Concepto {
                        nombre: $nombre,
                        policlinico: $policlinico
                    })
    
                    CREATE (r:Registro {
                        valor: $valor
                    })
    
                    MERGE (r)-[:REGISTRADO_EN]->(c)
                    MERGE (r)-[:CORRESPONDE_A]->(con)
                    """,
                    {
                        "cmf_nombre": cmf_nombre,
                        "policlinico": policlinico,
                        "nombre": nombre,
                        "valor": float(valor)
                    }
                )
    
        print(
            f"Grafo insertado correctamente: "
            f"{len(cmfs)} CMF, "
            f"{len(conceptos)} conceptos"
        )
