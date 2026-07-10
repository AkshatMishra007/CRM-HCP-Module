from typing import TypedDict

class GraphState(TypedDict):
    user_input:str
    extracted_data:dict
    summary:str
    suggestions:list[str]