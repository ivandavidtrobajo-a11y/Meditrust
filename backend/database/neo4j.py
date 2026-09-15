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

    def close(self):
        self.driver.close()


neo4j_connection = Neo4jConnection()
