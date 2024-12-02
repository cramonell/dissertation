# BUILTIN modules
import os
# Local modules
from utils.Graph2neo4j import GraphToNeo4jImporter
from utils.IFC2Graph import IfcToGraphConverter

def convert_ifc_to_neo4j(file: str, file_id, db_name = "neo4j", user_name = 'neo4j', password="PORTERO96"):
    
    path = None
    # check if file is UploadFile or a path
    path = file
    if not os.path.exists(path):
        print(f"ERROR: File '{path}' not found")
        return
    
    print(path)
    

    # Intantiate the ifc converter and the neo4j import classes. 
    # This will automatically transform the info of the IFC file into graph format and connect to the neo4j database service. 
    ifc_converter = IfcToGraphConverter(
        file = path,
        file_id = file_id
    )
    neo4j_importer = GraphToNeo4jImporter(
        nodes=ifc_converter.get_nodes(),
        relations=ifc_converter.get_relations(),
        db_name='neo4j',
        username='neo4j',
        password='password'
    )
    #insert nodes and relations to graphDB (neo4j)
    neo4j_importer.import_graph()

convert_ifc_to_neo4j(file="D:/UPC_PhD/01.Ashvin/DEMOS/DEMO-9/MUNICH-STADIUM/BIM/Munich_Roof.ifc",  file_id = 'MunichStadium')