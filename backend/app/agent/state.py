from typing import TypedDict, Optional

class GraphState(TypedDict):
    user_input: str

    intent: Optional[str]

    extracted_data: dict

    summary: str

    suggestions: list[str]