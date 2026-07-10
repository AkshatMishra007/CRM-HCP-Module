from app.agent import state
from langgraph.graph import StateGraph, END
from datetime import datetime

from app.agent.state import GraphState
from app.agent.prompts import EXTRACTION_PROMPT
from app.agent.llm import llm
from app.agent.parser import parse_json


def extract_information(state: GraphState):


    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
    Today's date is {today}.
    {EXTRACTION_PROMPT}
    User Input:
    {state["user_input"]}
""" 
    response = llm.invoke(prompt)

    print("\n========== RAW RESPONSE ==========")
    print(response.content)
    print("==================================\n")

    parsed = parse_json(response.content)

    print("\n========== PARSED JSON ==========")
    print(parsed)
    print("================================\n")

    return {
        "extracted_data": parsed
    }
def generate_summary(state:GraphState):
    prompt=f"""
    Summarize this HCP interaction in 2-3 sentences.
    Data:{state["extracted_data"]}
    """
    response=llm.invoke(prompt)
    return {
        "summary":response.content
    }

def generate_suggestions(state:GraphState):
    prompt=f"""
    Based on this interaction,suggest three follow-up actions.
    Interaction:
    {state["extracted_data"]}
    Return ONLY a JSON list.
    Example:
    [
    "Schedule follow-up meeting",
    "Share clinical paper",
    "Send product brochure"
    ]
    """
    response=llm.invoke(prompt)
    try:
        suggestions=parse_json(response.content)
    except:
        suggestions = []
    return {
        "suggestions": suggestions
    }

# Build the graph
builder = StateGraph(GraphState)

builder.add_node("extract", extract_information)
builder.add_node("summary", generate_summary)
builder.add_node("suggestions", generate_suggestions)

builder.set_entry_point("extract")

builder.add_edge("extract", "summary")
builder.add_edge("summary", "suggestions")
builder.add_edge("suggestions", END)

graph = builder.compile()