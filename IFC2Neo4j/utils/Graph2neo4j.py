# BUILTIN  modules
from typing import List, Dict, Any, Optional
import time
from uuid import UUID
import logging

# Third party modules
from neo4j import GraphDatabase


class GraphToNeo4jImporter():
    def __init__(self, nodes : Dict[str,Any], relations : Dict[str, Any], db_name: str, username: str="neo4j", password:str="PORTERO96", node_merge_params:Optional[List[str]]= None, rel_match_params:Optional[Dict[str, Any]] = None, uri:str ="bolt://localhost:7687", logger: logging.Logger = logging.getLogger(__name__)) -> None:

        self.logger =  logger
        self.driver= self.connect_database(username, password, uri, db_name)
        self.db_name=db_name
        self.session = None
        self.nodes = nodes
        self.relations = relations
        self.node_merge_params = node_merge_params # additional parameters to take into account to merge the new nodes
        self.relation_match_params = rel_match_params #  additional parameters to match nodes and establish relations
          
    def connect_database(self, username, password, uri, db_name):
        driver = GraphDatabase.driver(uri,
            auth=(username, password), database=db_name)

        driver.verify_connectivity()
        return driver

    def execute_query(self, query, parameters):
        
        with self.driver.session() as session:
            tx= session.begin_transaction()
            if not isinstance(query, list): query = [query]
            if not isinstance(parameters, list): parameters = [parameters]
            for i in range(len(query)):
                tx.run(query[i], parameters=parameters[i])
            tx.commit()
            self.logger.info('Total transactions = ' + str(len(query)))

    def create_neo4j_nodes(self):
        count = 0
        send_count =0
        queries = []
        parameters= []

        merge_params_sequence =None
        if self.node_merge_params:
            merge_params_sequence = ""
            for merge_param in self.node_merge_params:
                merge_params_sequence += f"{merge_param}: props.{merge_param},"
            merge_params_sequence = f"{{{merge_params_sequence[:-1]}}}"

        for node_type in self.nodes.keys():
            self.logger.info('Creating type '+ str(node_type) + ': ' + str(len(self.nodes[node_type])) + ' nodes')

            nodes = self.nodes[node_type]
            labels = nodes[0]['labels']
            label_sequence = ''
            for label in labels:
                label_sequence += ':' + label

            # Generar lista de propiedades
            params =[]
            for node in nodes:
                params.append(node['params'])
            
            # Ejecutar la peticion
            if merge_params_sequence:query = f"UNWIND $properties as props  MERGE (n {label_sequence} {merge_params_sequence}) SET n += props "  
            else:query = f"UNWIND $properties as props  CREATE (n {label_sequence}) SET n += props "
            
            send_count +=  len(nodes)
            if send_count < 10000:
                queries.append(query)
                parameters.append({'properties' : params})
            else:
                queries.append(query)
                parameters.append({'properties' : params})
                self.execute_query(queries, parameters = parameters)
                queries = []
                parameters = []
                send_count=0
            count += len(nodes)
        if send_count != 0: self.execute_query(queries, parameters = parameters)
        queries = []
        parameters = []
        send_count=0
        self.logger.info('Nodes: ' + str(count))
            
    def create_neo4j_relations(self): 
        count =0
        send_count =0
        queries = []
        parameters= []

        rel_match_sequence = None
        if self.relation_match_params:
            rel_match_sequence = ""
            for key in self.relation_match_params:
                rel_match_sequence += f"{key}: {self.relation_match_params[key]},"

        for rel_type in self.relations.keys():
            self.logger.info('Creating type '+ str(rel_type) + ': ' + str(len(self.relations[rel_type])) + ' relations')
            relations = self.relations[rel_type]

            if rel_match_sequence:  query = f" UNWIND $relations as relation MATCH (a{{GlobalId: relation.start,{rel_match_sequence[:-1]}}}) MATCH (b{{GlobalId: relation.end,{rel_match_sequence[:-1]}}}) WITH a, b MERGE (a)-[r:{rel_type}]->(b) "
            else: query = f" UNWIND $relations as relation MATCH (a{{GlobalId: relation.start}}) MATCH (b{{GlobalId: relation.end}}) WITH a, b MERGE (a)-[r:{rel_type}]->(b) "

            send_count +=  len(relations)
            if send_count < 10000:
                queries.append(query)
                parameters.append({'relations': relations})
            else:
                queries.append(query)
                parameters.append({'relations': relations})
                self.execute_query(queries, parameters = parameters)
                queries = []
                parameters = []
                send_count=0

            count += len(relations)
        if send_count != 0: self.execute_query(queries, parameters = parameters)   
        queries = []
        parameters = []
        send_count=0
        self.logger.info('Relations: '+ str(count))

    def import_graph(self):
        self.logger.info('Converting to Neo4j...')
        t= time.time()
        self.logger.info('Creating neo4j nodes...')
        self.create_neo4j_nodes()
        t = time.time()-t
        self.logger.info('Elapsed Time: ' + str(t) +' seconds')

        t = time.time()
        self.logger.info('Creating neo4j relations...')
        self.create_neo4j_relations()
        t = time.time()-t
        self.logger.info ('Elapsed Time: ' + str(t) +' seconds')

        self.logger.info('Convertion finished')

