import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util
import ifcopenshell.util.element, ifcopenshell.util.geolocation, ifcopenshell.util.doc
import json
from typing import Dict, List
from pydantic import FilePath
from schemas.schemas import Relation, Node
from uuid import UUID, uuid5, NAMESPACE_X500
import time
import logging

class IfcToGraphConverter():

    def __init__(self, file: str, file_id: int, logger: logging.Logger = logging.getLogger(__name__) ):
        self.logger = logger
        self.file: ifcopenshell.file = self.set_file(file)
        self.schema = ''
        self.project_id = str(UUID(ifcopenshell.guid.expand(self.file.by_type('IfcProject')[0].GlobalId)))
        self.file_id = file_id
        self.relations: dict = {}
        self.nodes:  dict = {}
        self.node_ids = []
        self.relation_ids = []
        self.RESOURCES = None
        self.RELATIONS = None
        self.NOT_USED_RESOURCES = []
        self.NOT_USED_ENTITIES = []
        
        self.set_relation_types()
        self.set_resources()
        self.set_nodes()
        self.set_relations()     
    
    def set_resources (self):
        self.logger.info('Setting resources...')
        if self.file.schema in ['IFC4', 'IFC4A1', 'IFC4A2', 'IFC4X1', 'IFC4X2', 'IFC4X3']:
            self.schema = 'IFC4'
            self.NOT_USED_RESOURCES = [
                "presentationAppearanceResource",
                "presentationDefinitionResource",
                "presentationOrganizationResource",
                "geometricConstraintResource",
                "geometricModelResource",
                "geometryResource",
                "topologyResource",
                "propertyResource",
                "quantityResource"
                ]
            with open('utils/resource_IFC4.json', 'r') as f:
                self.RESOURCES= json.load(f)
            f.close()
            for key in self.NOT_USED_RESOURCES:
                self.NOT_USED_ENTITIES+=self.RESOURCES[key]['entities']
                self.RESOURCES.pop(key)
      
        elif self.file.schema == 'IFC2X3':
            self.schema = 'IFC2X3'
            self.NOT_USED_RESOURCES = [
                "presentationAppearanceResource",
                "presentationDefinitionResource",
                "presentationDimensionResource",
                "presentationOrganizationResource",
                "presentationResource",
                "geometricConstraintResource",
                "geometricModelResource",
                "geometryResource",
                "topologyResource",
                "materialPropertyResource",
                "profilePropertyResource",
                "propertyResource",
                "quantityResource"
                ]
            with open('utils/resource_IFC2X3.json', 'r') as f:
                self.RESOURCES= json.load(f)
            f.close()
            for key in self.NOT_USED_RESOURCES:
                self.NOT_USED_ENTITIES+=self.RESOURCES[key]['entities']
                self.RESOURCES.pop(key)

    def set_relation_types(self):
        self.logger.info('Setting relation types...')
        with open('utils/relations.json', 'r') as f:
            self.RELATIONS = json.load(f)
        f.close()

    def set_file (self, file: str | ifcopenshell.file)-> ifcopenshell.file:
        if type(file) == str:
            return ifcopenshell.open(file)
        elif type(file)  == ifcopenshell.file:
            return file
        else: 
            msg="Type of file is not str of  ifcopenshell.file: "+ str(type(file))
            self.logger.exception(msg)
            raise TypeError
        
    
    def get_supertypes(self,entity_type:str):
                schema=ifcopenshell.ifcopenshell_wrapper.schema_by_name(self.file.schema)
                e = schema.declaration_by_name(entity_type)
                inheritance=[]
                while e.supertype():
                    inheritance.append(e.supertype().name())
                    e=e.supertype()
                for i in range(len(inheritance)):
                    inheritance[i]=inheritance[i]
                return inheritance
    
    def obj_to_uuid(self, obj: dict):
        hashable= []
        obj = obj

        def check(key, item, hashable):
            if isinstance(item, (str)):
                hashable.append(key+"="+item+",")
            elif isinstance(item,(list)):
                for i in item:
                    check(key, i, hashable)
            elif isinstance(item, (dict)):
                for key_ in item.keys():
                    check(key_, item[key_], hashable)
            else:
                hashable.append(key+"="+str(item)+",")
        for key in obj.keys():
            if obj[key]:
               check(key, obj[key], hashable)
        return uuid5(NAMESPACE_X500,''.join(hashable)[0:-1])

    def get_properties (self, entity: ifcopenshell.entity_instance):
        # This function gets all the psets in a single entity and collapse all of them into a single dictionary. 
        # This will avoid creating one node per pset and property, accessing property information
        # directly from the entity node
 
        try:
            psets = ifcopenshell.util.element.get_psets(entity)
        except Exception as  e:
            print(e)
            psets = None
        props = {}
        if psets:
            for pset in psets.keys():
                properties =psets[pset]
                id = properties.pop('id')    
                for property in properties.keys():
                    props[property]= properties[property]

        return props

    def create_node (self, entity: ifcopenshell.entity_instance):
        # This function recursively creates entity nodes and allowed resource nodes departing from an initial entity
        # get node info as a dict
        node_info= entity.get_info()
        # store and pop the ifc type
        node_type = node_info.pop('type')

        if 'id' in node_info.keys(): node_info.pop('id')
        # Make sure that the node has a globalId as UUID type. If not, create one hashing the data structure of the dict
        if 'GlobalId' not in node_info.keys(): 
            node_info['GlobalId'] = self.obj_to_uuid(node_info)
        else: 
            try: node_info['GlobalId'] = UUID(ifcopenshell.guid.expand(node_info['GlobalId']))
            except: pass
        if node_info['GlobalId'] not in self.node_ids:
        
            # Start creating the node if the class is used in the transformation configuration
            if node_type not in self.NOT_USED_ENTITIES:
                if 'OwnerHistory' in node_info.keys():  node_info.pop('OwnerHistory')
                if 'Representation' in node_info.keys():  node_info['Representation'] = True
                if 'HasPropertySets' in node_info.keys():  node_info.pop('HasPropertySets')
                
                #get properties from psets and psets of its types
                properties = self.get_properties(entity)
                #insert properties
                if properties:
                    for property in properties:
                        node_info[property] = properties[property]
                #  we add the ifc class as a property and the file id property
                node_info['IfcClass']= node_type
                node_info['file_id'] = self.file_id
                # Create labels including supertypes
                labels = [node_type] 
                try:
                    labels =  labels + self.get_supertypes(node_type) 
                except: pass

                # Check node attributes. If they reference other ifc entities we need to recursively create nodes
                keys_to_delete =[]
                for key in node_info.keys():
                    #if the info is a single ifc element, create the new node and correponding relations
                    if type(node_info[key]) == ifcopenshell.entity_instance:
                        new_entity = node_info[key]
                        keys_to_delete.append(key)
                        new_node_id = self.create_node(new_entity)
                        # create relation between current node andnew node with a type of 'has' + the attribute that relates both nodes
                        if new_node_id:
                            relation_id = str(node_info['GlobalId'])+str(new_node_id)
                            if relation_id not in self.relation_ids:                        
                                relation = Relation(type = 'has'+str(key), start = node_info['GlobalId'], end= new_node_id, params = None)
                                if 'has'+str(key) not in self.relations.keys():
                                    self.relations['has'+str(key)] = []
                                self.relations['has'+str(key)].append(relation.to_dict())
                                self.relation_ids.append(relation_id)
                    
                    #if the info is a list and contains ifc elements, iterate over it and do as previously
                    elif type(node_info[key]) == tuple and type(node_info[key][0]) == ifcopenshell.entity_instance:
                        keys_to_delete.append(key)
                        #do the same on each element of the list
                        for entity in node_info[key]:
                            new_node_id=self.create_node(entity)
                            if new_node_id:
                                relation_id = str(node_info['GlobalId'])+str(new_node_id)
                                if relation_id not in self.relation_ids:
                                    relation =Relation(type = 'has'+str(key), start = node_info['GlobalId'], end= new_node_id, params = None)
                                    if 'has'+str(key) not in self.relations.keys():
                                        self.relations['has'+str(key)] = []
                                    self.relations['has'+str(key)].append(relation.to_dict())
                                    self.relation_ids.append(relation_id)
                    
                # Delete those parts of the dict that reference ifc entities
                for key in keys_to_delete: node_info.pop(key)
                self.node_ids.append(node_info['GlobalId'])
                node = Node(labels = labels, params = node_info)
                if node_type not in self.nodes.keys():
                    self.nodes[node_type] = []
                self.nodes[node_type].append(node.to_dict())

                return node_info['GlobalId']
            else: return None
        else: return node_info['GlobalId']
 
    def create_contexts (self):
        # This function creates the context: project, geometric contexts, and units
        contexts = self.file.by_type('IfcContext')
        for context in contexts:
            self.create_node(context)

    def create_objects (self):
        # This function creates all the IfcObjects.
        # Each entity is one node in the graph.
        # Every node contains all the quantities and psets related to the entity

        objects = self.file.by_type('IfcObject')
        for object in objects:
            # TODO: manage simulations
            if object.is_a('IfcStructuralItem'): print(object)
            if object.is_a('IfcStructuralActivity'): print(object)
            #creates the node adding the properties
            self.create_node(object)

    def set_nodes(self) -> None:
        self.logger.info('Creating nodes...')
        t = time.time()
        # create contexts and objects
        if self.schema == 'IFC4': self.create_contexts()
        self.create_objects()
        t= time.time()-t
        self.logger.info('Time elapsed for  creating nodes: ' + str(t) + ' seconds')

    def set_relations(self) -> None:
        self.logger.info('Creating relations...')
        t1 = time.time()
        # we discard the relations of type IfcRelDefines.
        # They are related to types and properties, which we have handled in a different way
        if self.schema == "IFC4":
            rel_types = [
                'IfcRelAssigns', 
                'IfcRelAssociates', 
                'IfcRelConnects', 
                'IfcRelDeclares', 
                'IfcRelDecomposes',
                'IfcRelDefinesByType'
                ]
        elif self.schema == "IFC2X3":
            rel_types = [
                'IfcRelAssigns', 
                'IfcRelAssociates', 
                'IfcRelConnects', 
                'IfcRelDecomposes',
                'IfcRelDefinesByType'
                ]
        else: print('ERROR: SCHEMA NOT RECOGNIZED')
        relations = []
        for rel_type in rel_types:
            relations = relations + self.file.by_type(rel_type)
        
        for i in range(len(relations)):
            if relations[i].GlobalId not in self.relation_ids:
                self.relation_ids.append(relations[i].GlobalId)
                relation = relations[i].get_info()
                relation_tree = [relation['type']] + self.get_supertypes(relation['type']) 

                # set t to the key available in RELATIONS
                for t in relation_tree:
                    if t in self.RELATIONS.keys():
                        break

                # get the relation attributes, must be always 2, relating and related.
                graph_relation_types = []
                for k in self.RELATIONS[t].keys():
                    if k in relation.keys():
                        graph_relation_types.append(k)
                assert(len(graph_relation_types) == 2)
                
                # For convenience, make sure that relating and related elements are contained in lists. 
                if type(relation[graph_relation_types[0]])== ifcopenshell.entity_instance:
                        relation[graph_relation_types[0]] = [relation[graph_relation_types[0]]]
                        
                if type(relation[graph_relation_types[1]])== ifcopenshell.entity_instance:
                        relation[graph_relation_types[1]] = [relation[graph_relation_types[1]]]
                
                # create the relations in both senses.
                # if  the relation finds an entity that
                # is not transformed to a node, it creates it (this will happen with materials)
                if relation[graph_relation_types[0]] and relation[graph_relation_types[1]]:
                    # Relations from Node0 to Node1 
                    for entity_start in relation[graph_relation_types[0]]:
                        for entity_end in relation[graph_relation_types[1]]:

                            entity_start_info = entity_start.get_info()
                            entity_end_info = entity_end.get_info()

                            relation_type = self.RELATIONS[t][graph_relation_types[0]]

                            entity_start_id = self.create_node(entity_start)
                            entity_end_id =self.create_node(entity_end)

                            graph_relation = Relation(type = relation_type, start =entity_start_id, end = entity_end_id, params = None )

                            if  relation_type not in self.relations.keys():
                                self.relations[relation_type]=[]
                            self.relations[relation_type].append(graph_relation.to_dict())

                    # Relations from Node1 to Node0
                    for entity_start in relation[graph_relation_types[1]]:
                        for entity_end in relation[graph_relation_types[0]]:

                            entity_start_info = entity_start.get_info()
                            entity_end_info = entity_end.get_info()

                            relation_type = self.RELATIONS[t][graph_relation_types[1]]

                            entity_start_id = self.create_node(entity_start)
                            entity_end_id =self.create_node(entity_end)

                            graph_relation = Relation(type = relation_type, start =entity_start_id, end = entity_end_id, params = None )

                            if  relation_type not in self.relations.keys():
                                self.relations[relation_type]=[]
                            self.relations[relation_type].append(graph_relation.to_dict())
        t1 = time.time()-t1
        self.logger.info('Time elapsed for creating relations: ' + str(t1) +' seconds')

    def get_nodes(self) -> Dict[str, List[Node]]:
        return self.nodes
    
    def get_relations(self) -> Dict[str, List[Relation]]:
        return self.relations
    
    def get_project_id(self) -> str:
        return self.project_id
