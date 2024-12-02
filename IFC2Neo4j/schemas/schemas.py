from pydantic import BaseModel 
from typing import List, Dict,  Any,  Optional
from uuid import UUID, uuid4


def clean_key(s: str):
    symbols = {' ', "'", ";", ":", ",", "/", "-", ".", "(", ")", "[", "]", "=", "·", "#", "|", "\\", "@", "~", "%", "&", "$", "!", "¡", '"', "?", "¿", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}
    s = s.translate(str.maketrans("", "", ''.join(symbols)))
    if s == "" or s.replace(" ","") == "":
        return "null"
    return s
        
def clean_prop(s: Any) -> Any:
    if isinstance(s, str):
        s = s.translate(str.maketrans("", "", "'\""))
    elif isinstance(s,  UUID):
        s = str(s)
    return s

class Node(BaseModel):
    labels: List[str]
    params: Dict[str, Any]

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)
        __pydantic_self__.is_flat_dict()

    def is_flat_dict(__pydantic_self__):
        if __pydantic_self__.params:
            pop_list = []
            for key in __pydantic_self__.params.keys():
                if isinstance(__pydantic_self__.params[key], dict) or __pydantic_self__.params[key] == None:
                    pop_list.append(key)
            for key in pop_list:
               __pydantic_self__.params.pop(key)
    
    def to_dict(__pydantic_self__) -> Dict[str, Any]:
        node = {}
        node['labels'] = __pydantic_self__.labels
        node['params'] = {}
        for param in __pydantic_self__.params:
            node["params"][clean_key(param)] = clean_prop(__pydantic_self__.params[param])
        return node

class Relation(BaseModel):
    type: str
    start: UUID
    end: UUID
    params: Optional[Dict[str, Any]]

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)
        __pydantic_self__.is_flat_dict()

    def is_flat_dict(__pydantic_self__) -> bool:
        if __pydantic_self__.params:
            pop_list = []
            for key in __pydantic_self__.params.keys():
                if isinstance(__pydantic_self__.params[key], dict) or __pydantic_self__.params[key] == None:
                    pop_list.append(key)
            for key in pop_list:
                __pydantic_self__.params.pop(key)
                
    def to_dict(__pydantic_self__) -> Dict[str, Any]:
        relation = {}
        relation['type'] = __pydantic_self__.type
        relation['start'] = str(__pydantic_self__.start)
        relation['end'] = str(__pydantic_self__.end)
        relation['params'] = {}
        
        if __pydantic_self__.params:
            for param in __pydantic_self__.params:
                relation["params"][clean_key(param)] = clean_prop(__pydantic_self__.params[param])
        return relation
    
class Graph(BaseModel):
    nodes: Optional[List[Node]]
    relations: Optional[List[Relation]]

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

    def to_dict(__pydantic_self__) -> Dict[str, List[dict]]:
        n = []
        r = []
        for relation in __pydantic_self__.relations:
            d = relation.to_dict()
            d['start'] =  str(d['start'])
            d['end'] = str(d['end'])
            r.append(d)      
        return {'nodes': [node.to_dict() for node in __pydantic_self__.nodes], 'relations': r}
