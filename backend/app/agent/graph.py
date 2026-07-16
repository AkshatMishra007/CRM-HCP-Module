from typing import TypedDict, Dict, Any, List, Optional
from datetime import datetime
import re
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from app.agent.state import GraphState
from app.agent.prompts import EXTRACTION_PROMPT
from app.agent.llm import llm
from app.agent.parser import parse_json
from app.database import SessionLocal
from app.models.hcp import HCP
from app.models.interaction import Interaction
from app.models.material import Material
from app.models.sample import Sample
from app.models.ai_suggestion import AISuggestion


from dotenv import load_dotenv
from pathlib import Path
import os

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)
# Environment variables loaded dynamically



def normalize_interaction_type(itype: str) -> str:
    """
    Standardize the interaction type.
    """
    if not itype:
        return "Meeting"
    itype_lower = itype.lower()
    if any(keyword in itype_lower for keyword in ["meet", "in-person", "face", "discussion", "visit", "introduction"]):
        return "Meeting"
    if any(keyword in itype_lower for keyword in ["call", "phone", "tele", "speak"]):
        return "Call"
    if any(keyword in itype_lower for keyword in ["email", "mail", "write", "message"]):
        return "Email"
    if any(keyword in itype_lower for keyword in ["conf", "seminar", "symp"]):
        return "Conference"
    return "Meeting"


def parse_sample(sample_str: str):
    """
    Parses drug sample names and quantity.
    """
    sample_str = sample_str.strip()
    
    # 1. Parenthesized quantity at the end: e.g. "CardioX 10mg (5)" or "CardioX 10mg (5 sample packs)"
    match_paren = re.search(r"\((?P<qty>\d+)\s*[^)]*\)\s*$", sample_str, re.IGNORECASE)
    if match_paren:
        qty = int(match_paren.group("qty"))
        name = sample_str[:match_paren.start()].strip()
        return name, qty
        
    # 2. Prefix quantity like "5x CardioX", "5 samples of CardioX"
    match_prefix = re.match(r"^(?P<qty>\d+)\s*(?:x|X|samples?\s+of|packs?\s+of)\s+(?P<name>.+)", sample_str, re.IGNORECASE)
    if match_prefix:
        qty = int(match_prefix.group("qty"))
        name = match_prefix.group("name").strip()
        return name, qty
        
    # 3. Simple prefix number (e.g., "5 CardioX 10mg") that does not represent dosage unit
    match_simple_prefix = re.match(r"^(?P<qty>\d+)\s+(?!(?:mg|mcg|g|ml|tabs?|caps?)\b)(?P<name>.+)", sample_str, re.IGNORECASE)
    if match_simple_prefix:
        qty = int(match_simple_prefix.group("qty"))
        name = match_simple_prefix.group("name").strip()
        return name, qty
        
    return sample_str, 1


def normalize_sentiment(sentiment: Optional[str]) -> Optional[str]:
    """
    Normalize sentiment text into strict values: Positive, Negative, Neutral.
    """
    if not sentiment:
        return "Neutral"
    s = sentiment.strip().lower()
    if "positive" in s:
        return "Positive"
    if "negative" in s:
        return "Negative"
    if "neutral" in s:
        return "Neutral"
    return "Neutral"


def format_doctor_name(name: str) -> str:
    """
    Ensure the name starts with "Dr. " exactly once, and doesn't get duplicated.
    """
    clean = name.strip()
    clean_no_dr = re.sub(r"^(Dr\.\s*|Dr\s+)", "", clean, flags=re.IGNORECASE).strip()
    return f"Dr. {clean_no_dr}"


def extract_hcp_name(user_input: str) -> str:
    """
    Ask LLM to extract the doctor's name from user input and return it clean.
    Never recursively calls itself.
    """
    prompt = f"""
Extract the doctor's name from the user's request.

Return ONLY valid JSON.

Example:
{{
    "hcp_name": "Dr. Amit Sharma"
}}

User Request:
{user_input}
"""
    response = llm.invoke(prompt)
    parsed = parse_json(response.content)
    return parsed.get("hcp_name", "").strip()


def get_hcp(db: Session, doctor_name: str) -> Optional[HCP]:
    """
    Retrieve HCP object by name. Trim spaces, case-insensitive, strips doctor prefix.
    """
    name_clean = doctor_name.strip()
    if not name_clean:
        return None
    name_search = re.sub(r"^(Dr\.\s*|Dr\s+)", "", name_clean, flags=re.IGNORECASE).strip()
    hcp = db.query(HCP).filter(HCP.name.ilike(name_clean)).first()
    if not hcp and name_search:
        hcp = db.query(HCP).filter(HCP.name.ilike(f"%{name_search}%")).first()
    return hcp


def get_history(db: Session, hcp_id: int) -> List[Interaction]:
    """
    Fetch interaction history sorted newest first.
    """
    return db.query(Interaction).filter(Interaction.hcp_id == hcp_id).order_by(
        Interaction.interaction_date.desc(),
        Interaction.created_at.desc(),
        Interaction.id.desc()
    ).all()


def serialize_interaction(item: Interaction) -> Dict[str, Any]:
    """
    Convert Interaction model record into a serializable dictionary.
    """
    return {
        "id": item.id,
        "hcp_id": item.hcp_id,
        "interaction_type": item.interaction_type or "",
        "interaction_date": str(item.interaction_date) if item.interaction_date else "",
        "interaction_time": str(item.interaction_time) if item.interaction_time else "",
        "meeting_location": item.meeting_location or "",
        "attendees": item.attendees or "",
        "topics_discussed": item.topics_discussed or "",
        "ai_summary": item.ai_summary or "",
        "sentiment": item.sentiment or "",
        "outcomes": item.outcomes or "",
        "follow_up_actions": item.follow_up_actions or "",
        "materials": [{"material_name": m.material_name} for m in item.materials],
        "samples": [{"sample_name": s.sample_name, "quantity": s.quantity} for s in item.samples],
        "ai_suggestions": [{"suggestion": sug.suggestion} for sug in item.ai_suggestions]
    }


def safe_parse_list(response: str) -> List[str]:
    """
    Safely parse a JSON list from an LLM response without assuming the main parser handles arrays.
    """
    response_clean = response.strip()
    match = re.search(r"\[.*\]", response_clean, re.DOTALL)
    if match:
        try:
            import json
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed]
        except Exception:
            pass
            
    items = []
    for line in response_clean.split("\n"):
        line_clean = line.strip().strip('"').strip("'").strip(",").strip("-").strip("*").strip()
        if line_clean and not line_clean.startswith("[") and not line_clean.endswith("]"):
            items.append(line_clean)
    return items[:5]


def detect_intent(state: GraphState) -> Dict[str, Any]:
    """
    Classifies the user input intent with strict validation.
    """
    user_input = state.get("user_input", "")
    prompt = f"""
    You are an intelligent routing agent for a life sciences HCP CRM.

    Analyze the user request.

    Return ONLY one word.

    log
    edit
    history
    summary
    next_action
    unknown

    User:
    {user_input}
    """
    response = llm.invoke(prompt)
    intent = response.content.strip().lower()
    
    valid_intents = {"log", "edit", "history", "summary", "next_action", "unknown"}
    if intent not in valid_intents:
        intent = "unknown"
        
    if intent == "unknown":
        intent = "log"
        
    return {
        "intent": intent
    }


def log_interaction(state: GraphState) -> Dict[str, Any]:
    """
    Extraction pipeline for logging new interactions.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Today's date is {today}.
    {EXTRACTION_PROMPT}
    User Input:
    {state["user_input"]}
    """
    response = llm.invoke(prompt)
    parsed = parse_json(response.content)
    
    if not parsed:
        return {
            "extracted_data": {},
            "summary": "I couldn't extract interaction details from your request.",
            "suggestions": []
        }
        
    if "sentiment" in parsed:
        parsed["sentiment"] = normalize_sentiment(parsed["sentiment"])
    if "interaction_type" in parsed:
        parsed["interaction_type"] = normalize_interaction_type(parsed["interaction_type"])
        
    summary_prompt = f"""
    Summarize this HCP interaction in 2-3 sentences.
    Data: {parsed}
    """
    summary_res = llm.invoke(summary_prompt)
    summary = summary_res.content.strip()
    
    sug_prompt = f"""
    Based on this interaction, suggest three follow-up actions.
    Interaction:
    {parsed}
    Return ONLY a JSON list.
    Example:
    [
      "Schedule follow-up meeting",
      "Share clinical paper",
      "Send product brochure"
    ]
    """
    sug_res = llm.invoke(sug_prompt)
    suggestions = safe_parse_list(sug_res.content)
    
    return {
        "extracted_data": parsed,
        "summary": summary,
        "suggestions": suggestions
    }


def edit_interaction(state: GraphState) -> Dict[str, Any]:
    """
    Retrieve and update modified fields on the doctor's latest interaction log.
    """
    prompt = f"""
    You are an AI assistant that extracts the doctor's name and specific updates from a user request.
    Extract the doctor's name and return ONLY a valid JSON object with:
    - "hcp_name": Name of the doctor.
    - "updates": A JSON dictionary of fields to be updated. Do not include any field not mentioned to be changed.
    
    Possible update fields:
    - "interaction_type": "Meeting" | "Call" | "Email" | "Conference"
    - "interaction_date": "YYYY-MM-DD"
    - "interaction_time": "HH:MM"
    - "meeting_location": "new location"
    - "attendees": "new attendees string"
    - "topics_discussed": "new topics discussed"
    - "sentiment": "Positive" | "Neutral" | "Negative"
    - "outcomes": "new outcomes"
    - "follow_up_actions": "new follow-up actions"
    - "materials_shared": ["List of material names"]
    - "samples_distributed": ["List of sample strings, e.g. '5 samples of CardioX'"]
    - "ai_suggestions": ["List of suggestion texts"]
    
    User Input: {state["user_input"]}
    
    Return ONLY valid JSON.
    """
    response = llm.invoke(prompt)
    parsed = parse_json(response.content)
    hcp_name = parsed.get("hcp_name", "").strip()
    updates = parsed.get("updates", {})
    
    db = SessionLocal()
    try:
        if not hcp_name:
            hcp_name = extract_hcp_name(state["user_input"])
            
        if not hcp_name:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        hcp = get_hcp(db, hcp_name)
        if not hcp:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        latest = db.query(Interaction).filter(Interaction.hcp_id == hcp.id).order_by(
            Interaction.interaction_date.desc(),
            Interaction.created_at.desc(),
            Interaction.id.desc()
        ).first()
        
        if not latest:
            return {
                "extracted_data": {},
                "summary": f"No interactions found for {format_doctor_name(hcp.name)} to edit.",
                "suggestions": []
            }
            
        core_fields = [
            "interaction_type", "interaction_date", "interaction_time",
            "meeting_location", "attendees", "topics_discussed",
            "sentiment", "outcomes", "follow_up_actions"
        ]
        
        for field in core_fields:
            if field in updates:
                val = updates[field]
                if field == "interaction_date" and val:
                    try:
                        val = datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
                    except Exception:
                        pass
                elif field == "interaction_time" and val:
                    try:
                        val = datetime.strptime(str(val).strip(), "%H:%M").time()
                    except Exception:
                        pass
                elif field == "interaction_type" and val:
                    val = normalize_interaction_type(str(val))
                elif field == "sentiment" and val:
                    val = normalize_sentiment(str(val))
                setattr(latest, field, val)
                
        if "materials_shared" in updates:
            db.query(Material).filter(Material.interaction_id == latest.id).delete()
            for name in updates["materials_shared"]:
                if str(name).strip():
                    db.add(Material(interaction_id=latest.id, material_name=str(name).strip()))
                    
        if "samples_distributed" in updates:
            db.query(Sample).filter(Sample.interaction_id == latest.id).delete()
            for sample_str in updates["samples_distributed"]:
                if str(sample_str).strip():
                    name, qty = parse_sample(str(sample_str))
                    db.add(Sample(interaction_id=latest.id, sample_name=name, quantity=qty))
                    
        if "ai_suggestions" in updates:
            db.query(AISuggestion).filter(AISuggestion.interaction_id == latest.id).delete()
            for sug in updates["ai_suggestions"]:
                if str(sug).strip():
                    db.add(AISuggestion(interaction_id=latest.id, suggestion=str(sug).strip()))
                    
        db.commit()
        db.refresh(latest)
        db.expire(latest, ["materials", "samples", "ai_suggestions"])
        
        serialized = serialize_interaction(latest)
        
        suggestions = [sug["suggestion"] for sug in serialized["ai_suggestions"]]

        prompt = f"""
        You are an AI CRM assistant.

        A sales representative updated an HCP interaction.

        Doctor: {format_doctor_name(hcp.name)}

        Updated fields:
        {updates}

        Write a professional confirmation message.

        The response should include:
        - A success confirmation.
        - Doctor's name.
        - A bullet list of the updated fields.
        - A one-line conclusion.

        Return plain text only.
        """

        summary = llm.invoke(prompt).content

        return {
            "extracted_data": {
                "interaction_id": latest.id,
                "updated_fields": updates,
                "current_state": serialized
            },
            "summary": summary,
            "suggestions": [sug["suggestion"] for sug in serialized["ai_suggestions"]]
        }
                
    except Exception as e:
        db.rollback()
        import traceback
        print(f"Error in edit_interaction: {e}")
        traceback.print_exc()
        return {
            "extracted_data": {},
            "summary": f"Error updating interaction: {str(e)}",
            "suggestions": []
        }
    finally:
        db.close()


def search_history(state: GraphState) -> Dict[str, Any]:
    """
    Search HCP and list past interactions without summarizing.
    """
    hcp_name = extract_hcp_name(state["user_input"])
    
    db = SessionLocal()
    try:
        if not hcp_name:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        hcp = get_hcp(db, hcp_name)
        if not hcp:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        history = get_history(db, hcp.id)
        serialized_history = [serialize_interaction(item) for item in history]
        
        md_lines = [f"### Interaction History for {format_doctor_name(hcp.name)}"]
        for idx, h in enumerate(serialized_history, start=1):
            date_val = h.get("interaction_date") or "No Date"
            type_val = h.get("interaction_type") or "Meeting"
            loc_val = h.get("meeting_location") or "N/A"
            topics_val = h.get("topics_discussed") or "N/A"
            sentiment_val = h.get("sentiment") or "Neutral"
            outcome_val = h.get("outcomes") or "N/A"
            follow_val = h.get("follow_up_actions") or "N/A"
            
            sentiment_emoji = "🟢 Positive" if "pos" in sentiment_val.lower() else "🔴 Negative" if "neg" in sentiment_val.lower() else "🟡 Neutral"
            
            md_lines.append(
                f"**{idx}. {date_val} — {type_val}** ({loc_val})\n"
                f"- **Sentiment:** {sentiment_emoji}\n"
                f"- **Topics:** {topics_val}\n"
                f"- **Outcome:** {outcome_val}\n"
                f"- **Follow-up:** {follow_val}"
            )
        summary_md = "\n\n".join(md_lines)
        
        return {
            "extracted_data": {
                "history": serialized_history
            },
            "summary": summary_md,
            "suggestions": []
        }
    except Exception:
        return {
            "extracted_data": {},
            "summary": "Doctor not found.",
            "suggestions": []
        }
    finally:
        db.close()


def generate_summary(state: GraphState) -> Dict[str, Any]:
    """
    Analyze complete history of database interactions and write relationship details.
    """
    hcp_name = extract_hcp_name(state["user_input"])
    
    db = SessionLocal()
    try:
        if not hcp_name:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        hcp = get_hcp(db, hcp_name)
        if not hcp:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        history = get_history(db, hcp.id)
        if not history:
            return {
                "extracted_data": {},
                "summary": "No interaction history found.",
                "suggestions": []
            }
            
        history_details = []
        for idx, item in enumerate(history):
            mats = [m.material_name for m in item.materials]
            samps = [f"{s.quantity}x {s.sample_name}" for s in item.samples]
            history_details.append(
                f"Interaction {idx + 1}:\n"
                f"- Date: {item.interaction_date}\n"
                f"- Type: {item.interaction_type}\n"
                f"- Topics: {item.topics_discussed}\n"
                f"- Sentiment: {item.sentiment}\n"
                f"- Outcomes: {item.outcomes}\n"
                f"- Follow-up: {item.follow_up_actions}\n"
                f"- Materials: {mats}\n"
                f"- Samples: {samps}\n"
            )
            
        history_data = "\n\n".join(history_details)
        
        summary_prompt = f"""
        You are an AI CRM Relationship Intelligence Assistant for a pharmaceutical company.

        Analyze ONLY the interaction history provided below.

        Generate a professional CRM Relationship Report.

        The report must use EXACTLY the following sections.

        # Relationship Summary – {format_doctor_name(hcp.name)}

        ## Executive Overview
        Write 2-3 sentences summarizing the overall relationship with the doctor.

        ## Interaction Snapshot
        Include:
        - Total Interactions
        - Latest Interaction Date
        - Products Discussed
        - Overall Sentiment
        - Current Relationship Stage (Cold / Developing / Engaged / Strong)

        ## Discussion Highlights
        Summarize the major products, topics, objections, requests, and discussions across all meetings.

        ## Relationship Assessment
        Explain how the relationship has evolved based on the interaction history.
        Mention whether engagement is increasing, decreasing, or stable.

        ## Pending Follow-ups
        List all pending follow-up actions.

        ## Recommendations for the Representative
        Provide exactly 5 actionable recommendations.

        ## Priority Level
        Choose ONE:
        🟢 High
        🟡 Medium
        🔴 Low

        Explain WHY this priority was assigned.

        Rules:
        - Do NOT invent information.
        - Use only the interaction history below.
        - Keep the tone professional.
        - Return plain Markdown text.
        - Do not return JSON.

        Interaction History:

        {history_data}
        """
        summary_res = llm.invoke(summary_prompt)
        
        return {
            "extracted_data": {},
            "summary": summary_res.content.strip(),
            "suggestions": []
        }
    except Exception:
        return {
            "extracted_data": {},
            "summary": "Doctor not found.",
            "suggestions": []
        }
    finally:
        db.close()


def suggest_next_action(state: GraphState) -> Dict[str, Any]:
    """
    Recommend 3-5 next actions based on past DB logs.
    """
    hcp_name = extract_hcp_name(state["user_input"])
    
    db = SessionLocal()
    try:
        if not hcp_name:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        hcp = get_hcp(db, hcp_name)
        if not hcp:
            return {
                "extracted_data": {},
                "summary": "Doctor not found.",
                "suggestions": []
            }
            
        history = get_history(db, hcp.id)
        if not history:
            return {
                "extracted_data": {},
                "summary": "No previous interactions found.",
                "suggestions": ["No previous interactions found."]
            }
            
        history_details = []
        for idx, item in enumerate(history):
            history_details.append(
                f"Interaction {idx + 1}:\n"
                f"- Date: {item.interaction_date}\n"
                f"- Topics: {item.topics_discussed}\n"
                f"- Outcomes: {item.outcomes}\n"
                f"- Follow-up: {item.follow_up_actions}\n"
            )
        history_data = "\n\n".join(history_details)
        
        suggest_prompt = f"""
        You are a senior pharmaceutical sales assistant.
        Review the interaction history for {format_doctor_name(hcp.name)} and recommend 3-5 actionable next suggestions.
        Specifically recommend:
        - The next visit/meeting or follow-up call focus
        - Samples to carry/distribute
        - Brochures to share
        - Clinical papers to email/present
        - Meeting focus
        - Relationship risks
        - Prioritization level
        
        Return ONLY a JSON array of strings (3 to 5 items). Do not include any explanations, introduction, or other formatting.
        Example output format:
        [
          "Schedule follow-up next Tuesday",
          "Carry 10 CardioX samples",
          "Share hypertension clinical study"
        ]
        
        History Data:
        {history_data}
        """
        sug_res = llm.invoke(suggest_prompt)
        suggestions = safe_parse_list(sug_res.content)
        
        summary_md = f"### Actionable Recommendations for {format_doctor_name(hcp.name)}\n\n"
        for idx, sug in enumerate(suggestions, start=1):
            summary_md += f"**{idx}.** {sug}\n"
            
        return {
            "extracted_data": {},
            "summary": summary_md,
            "suggestions": suggestions
        }
    except Exception:
        return {
            "extracted_data": {},
            "summary": "Doctor not found.",
            "suggestions": []
        }
    finally:
        db.close()


def handle_unknown(state: GraphState) -> Dict[str, Any]:
    """
    Handle unknown intents. Default log logic will avoid reaching here.
    """
    return {
        "extracted_data": {},
        "summary": "I couldn't identify the request. You can try saying:\n"
                   "- 'Log interaction with Dr. Sharma'\n"
                   "- 'Edit last interaction with Dr. Sharma'\n"
                   "- 'Show history for Dr. Sharma'\n"
                   "- 'Summarize meetings for Dr. Sharma'\n"
                   "- 'Suggest next action for Dr. Sharma'",
        "suggestions": []
    }


def route_intent(state: GraphState) -> str:
    """
    Route based on classified intent.
    """
    intent = state.get("intent", "unknown")
    if intent == "log":
        return "log_interaction"
    elif intent == "edit":
        return "edit_interaction"
    elif intent == "history":
        return "search_history"
    elif intent == "summary":
        return "generate_summary"
    elif intent == "next_action":
        return "suggest_next_action"
    else:
        return "handle_unknown"


# Build the graph
builder = StateGraph(GraphState)

builder.add_node("detect_intent", detect_intent)
builder.add_node("log_interaction", log_interaction)
builder.add_node("edit_interaction", edit_interaction)
builder.add_node("search_history", search_history)
builder.add_node("generate_summary", generate_summary)
builder.add_node("suggest_next_action", suggest_next_action)
builder.add_node("handle_unknown", handle_unknown)

builder.set_entry_point("detect_intent")

builder.add_conditional_edges(
    "detect_intent",
    route_intent,
    {
        "log_interaction": "log_interaction",
        "edit_interaction": "edit_interaction",
        "search_history": "search_history",
        "generate_summary": "generate_summary",
        "suggest_next_action": "suggest_next_action",
        "handle_unknown": "handle_unknown"
    }
)

builder.add_edge("log_interaction", END)
builder.add_edge("edit_interaction", END)
builder.add_edge("search_history", END)
builder.add_edge("generate_summary", END)
builder.add_edge("suggest_next_action", END)
builder.add_edge("handle_unknown", END)

graph = builder.compile()