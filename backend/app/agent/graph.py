import json
import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Any
from langgraph.graph import StateGraph, START, END

from app.database import SessionLocal
from app.agent.llm import llm
from app.agent.state import GraphState, ToolType
from app.agent.prompts import (
    INTENT_PROMPT,
    EXTRACTION_PROMPT,
    EDIT_PROMPT,
    HCP_NAME_PROMPT,
    LOG_SUMMARY_PROMPT,
    RELATIONSHIP_SUMMARY_PROMPT,
    SUGGESTION_PROMPT,
    NEXT_ACTION_PROMPT,
    QUESTION_PROMPT,
    EDIT_CONFIRMATION_PROMPT
)
from app.agent.session import (
    SESSION_STORE,
    SESSION_LOCK,
    get_or_create_session,
    extract_hcp_name,
    clear_doctor_session_mapping
)
from app.agent.routing import (
    route_after_detect_intent,
    route_by_validation,
    route_by_tool_status
)
from app.agent.parser import parse_json
from app.tools.crm_tools import (
    db_search_hcp,
    db_create_hcp,
    db_save_interaction,
    db_save_samples,
    db_save_materials,
    db_save_suggestions,
    db_update_interaction,
    db_get_history,
    execute_save,
    execute_update,
    execute_query,
    db_update_summary,
    db_update_suggestions,
    normalize_hcp_name
)
from app.routers.interaction import parse_sample as parse_sample_helper, normalize_interaction_type
from app.models.interaction import Interaction

# Setup Logger
logger = logging.getLogger("hcp_crm_graph")
logging.basicConfig(level=logging.INFO)

# Node Implementations

def load_session_node(state: GraphState) -> dict:
    """
    Loads persistent session state dictionary from SESSION_STORE using 
    the active session key, merging in the user's latest text input.
    """
    user_input = state.get("user_input") or ""
    session_id_arg = state.get("session_id")
    session_id = get_or_create_session(user_input, session_id_arg)
    
    with SESSION_LOCK:
        session_data = SESSION_STORE[session_id].copy()
        
    session_data["user_input"] = user_input
    session_data["user_message"] = user_input
    session_data["current_node"] = "LoadSession"
    session_data["workflow_stage"] = "Session Loaded"
    
    logger.info("=" * 80)
    logger.info("[LoadSession]")
    logger.info(f"Session ID      : {session_id}")
    logger.info(f"Incoming Message: {user_input}")
    logger.info(f"Loaded Draft    : {json.dumps(session_data.get('interaction_draft', {}), indent=2)}")
    logger.info(f"Interaction Status: {session_data.get('interaction_status')}")
    logger.info("=" * 80)
    logger.info(f"[Node=LoadSession] SessionId={session_id} Input='{user_input[:40]}...'")
    return session_data

def initialize_request_node(state: GraphState) -> dict:
    """
    Resets request-scoped variables at the start of a request execution.
    """
    return {
        "response": "",
        "summary": None,
        "suggestions": [],
        "tool_result": None,
        "normalized_tool_result": None,
        "error_message": None,
        "validation_errors": [],
        "missing_fields": [],
        "intent": None,
        "newly_extracted_entities": {},
        "tool_to_execute": None,
        "interaction_complete": False,
        "current_node": "InitializeRequest",
        "workflow_stage": "Request Initialized"
    }

def resume_draft_node(state: GraphState) -> dict:
    """
    Restores the draft workflow details, ensuring status shifts to 
    IN_PROGRESS if a draft exists and context matches.
    """
    draft = state.get("interaction_draft") or {}
    status = state.get("interaction_status") or "EMPTY"
    
    if draft and status == "EMPTY":
        status = "IN_PROGRESS"
        
    logger.info(f"[Node=ResumeDraft] SessionId={state.get('session_id')} InteractionStatus={status} DraftKeys={list(draft.keys())}")
    return {
        "interaction_status": status,
        "current_node": "ResumeDraft",
        "workflow_stage": "Draft Resumed"
    }

def retrieve_context_node(state: GraphState) -> dict:
    """
    Gathers conversational history, slicing the list down to the 
    last 10 turns to save LLM tokens.
    """
    history = state.get("conversation_history") or []
    recent_history = history[-10:]
    
    logger.info(f"[Node=RetrieveContext] SessionId={state.get('session_id')} HistorySize={len(history)} -> SlicedSize={len(recent_history)}")
    return {
        "conversation_history": recent_history,
        "current_node": "RetrieveContext",
        "workflow_stage": "Context Retrieved"
    }

def detect_intent_node(state: GraphState) -> dict:
    """
    Invokes the classification model using INTENT_PROMPT to categorize 
    the user's request into one of the 6 core intents.
    """
    prompt = INTENT_PROMPT.format(user_message=state["user_message"])
    response = llm.invoke(prompt)
    intent = response.content.strip().upper()
    
    msg_lower = state["user_message"].lower()
    
    # Check for discard intent first
    if "discard" in msg_lower:
        intent = "DISCARD_DRAFT"
    
    # Heuristics mapping fallback to protect intent classification checks
    allowed = ["LOG_INTERACTION", "SAVE_INTERACTION", "UPDATE_INTERACTION", "SEARCH_HISTORY", "GET_SUMMARY", "GENERAL_CHAT", "DISCARD_DRAFT"]
    if intent not in allowed:
        if "save" in msg_lower:
            intent = "SAVE_INTERACTION"
        elif "update" in msg_lower or "edit" in msg_lower:
            intent = "UPDATE_INTERACTION"
        elif "history" in msg_lower or "previous" in msg_lower:
            intent = "SEARCH_HISTORY"
        elif "summary" in msg_lower or "relationship" in msg_lower or "next best action" in msg_lower or "suggest" in msg_lower:
            intent = "GET_SUMMARY"
        elif "met" in msg_lower or "log" in msg_lower or "visit" in msg_lower:
            intent = "LOG_INTERACTION"
        else:
            intent = "GENERAL_CHAT"

    current_status = state.get("interaction_status") or "EMPTY"
    current_workflow = state.get("workflow_state") or "NONE"


    _CONTEXT_SWITCH_KEYWORDS = {
        "save", "update", "edit", "history", "previous",
        "summary", "relationship", "discard", "cancel"
    }
    if current_status == "READY_TO_SAVE" and intent == "GENERAL_CHAT":
        if not any(kw in msg_lower for kw in _CONTEXT_SWITCH_KEYWORDS):
            intent = "LOG_INTERACTION"
            logger.info(f"[Node=DetectIntent] BUG-003 deterministic override: GENERAL_CHAT → LOG_INTERACTION (status=READY_TO_SAVE, no context-switch keyword)")


    if current_status == "READY_TO_SAVE" and intent in ["SEARCH_HISTORY", "GET_SUMMARY", "UPDATE_INTERACTION"]:
        intent = "UNSAVED_DRAFT_PROTECTION"
        
    if current_workflow == "WAITING_CONFIRMATION":
        if any(w in msg_lower for w in ["yes", "confirm", "apply", "ok"]):
            intent = "CONFIRM_UPDATE"
        elif any(w in msg_lower for w in ["no", "cancel", "discard"]):
            intent = "CANCEL_UPDATE"
        else:
            intent = "CONFIRMATION_REQUIRED"
            
    logger.info(f"[Node=DetectIntent] SessionId={state.get('session_id')} ClassifiedIntent={intent}")
    return {
        "intent": intent,
        "current_node": "DetectIntent",
        "workflow_stage": f"Intent Detected: {intent}"
    }

def extract_json_node(state: GraphState) -> dict:
    """
    Uses LLM structure extraction to return raw, un-normalized key-value pairs 
    from natural language sentences.
    """
    draft = state.get("interaction_draft") or {}
    msg = state["user_message"]
    
    prompt = EXTRACTION_PROMPT.format(user_message=msg, interaction_draft=json.dumps(draft))
        
    response = llm.invoke(prompt)
    parsed = parse_json(response.content)
    logger.info("=" * 80)
    logger.info("[ExtractJSON]")
    logger.info("Draft sent to LLM:")
    logger.info(json.dumps(draft, indent=2))
    logger.info("User Message:")
    logger.info(msg)
    logger.info("Prompt:")
    logger.info(prompt)
    logger.info("Raw LLM Response:")
    logger.info(response.content)
    logger.info("Parsed JSON:")
    logger.info(json.dumps(parsed, indent=2))
    logger.info("=" * 80)
    logger.info(f"[Node=ExtractJSON] SessionId={state.get('session_id')} ExtractedKeys={list(parsed.keys())}")
    return {
        "newly_extracted_entities": parsed,
        "current_node": "ExtractJSON",
        "workflow_stage": "JSON Extracted"
    }

def normalize_sentiment(val: str) -> str:
    """Standardizes sentiment strings."""
    if not val:
        return "Neutral"
    val_lower = val.lower()
    if "pos" in val_lower or "interest" in val_lower or "happy" in val_lower:
        return "Positive"
    if "neg" in val_lower or "reject" in val_lower or "dis" in val_lower:
        return "Negative"
    return "Neutral"

def normalize_fields_node(state: GraphState) -> dict:
    """
    Runs deterministic Python conversions to sanitize date, time, 
    sentiment, and sample count inputs.
    """
    entities = state.get("newly_extracted_entities") or {}
    intent = state.get("intent")
    
    normalized = entities.copy()
    
    if "hcp_name" in normalized and normalized["hcp_name"]:
        normalized["hcp_name"] = normalize_hcp_name(normalized["hcp_name"])
            
    if intent == "LOG_INTERACTION" or state.get("interaction_status") in ["IN_PROGRESS", "READY_TO_SAVE"]:
        # Normalize date dynamically using system date
        if normalized.get("interaction_date"):
            d_str = normalized["interaction_date"].lower()
            if "today" in d_str:
                normalized["interaction_date"] = date.today().isoformat()
            elif "yesterday" in d_str:
                normalized["interaction_date"] = (date.today() - timedelta(days=1)).isoformat()
            elif not re.match(r"^\d{4}-\d{2}-\d{2}$", normalized["interaction_date"]):
                normalized["interaction_date"] = ""
        
        # Normalize time
        if normalized.get("interaction_time"):
            t_str = normalized["interaction_time"]
            if ":" in t_str:
                parts = t_str.split(":")
                if len(parts) == 2:
                    try:
                        h, m = int(parts[0]), int(parts[1])
                        normalized["interaction_time"] = f"{h:02d}:{m:02d}"
                    except ValueError:
                        normalized["interaction_time"] = ""
            else:
                normalized["interaction_time"] = ""
                
        # Normalize sentiment
        if "sentiment" in normalized:
            normalized["sentiment"] = normalize_sentiment(normalized["sentiment"])
            
        # Normalize interaction type
        if "interaction_type" in normalized:
            normalized["interaction_type"] = normalize_interaction_type(normalized["interaction_type"])
        else:
            # BUG-008 / M-2: If interaction_type was not explicitly extracted but the message contains
            # clear verbs like "met" or "visited", infer it so incremental logging doesn't get blocked.
            user_msg_lower = (state.get("user_message") or "").lower()
            if any(w in user_msg_lower for w in ["met", "visit", "in-person", "saw"]):
                normalized["interaction_type"] = "Meeting"
            elif any(w in user_msg_lower for w in ["called", "phone", "spoke"]):
                normalized["interaction_type"] = "Call"
            elif any(w in user_msg_lower for w in ["emailed", "wrote"]):
                normalized["interaction_type"] = "Email"
            
        # Normalize sample arrays
        if "samples_distributed" in normalized and isinstance(normalized["samples_distributed"], list):
            norm_samples = []
            for s in normalized["samples_distributed"]:
                name, qty = parse_sample_helper(s)
                norm_samples.append(f"{qty} {name}")
            normalized["samples_distributed"] = norm_samples
            
    logger.info("=" * 80)
    logger.info("[NormalizeFields]")
    logger.info("Before:")
    logger.info(json.dumps(entities, indent=2))
    logger.info("After:")
    logger.info(json.dumps(normalized, indent=2))
    logger.info("=" * 80)
    logger.info(f"[Node=NormalizeFields] SessionId={state.get('session_id')} NormalizedKeys={list(normalized.keys())}")
    return {
        "newly_extracted_entities": normalized,
        "current_node": "NormalizeFields",
        "workflow_stage": "Fields Normalized"
    }

def merge_draft_node(state: GraphState) -> dict:
    """
    Progressively integrates newly normalized fields into the main draft object 
    without erasing previously gathered information.
    
    BUG-006: list fields (materials_shared, samples_distributed) are merged
    by appending unique values; scalar fields continue to fully replace.
    """
    intent = state.get("intent")
    entities = state.get("newly_extracted_entities") or {}
    draft = (state.get("interaction_draft") or {}).copy()
    
    # Fields that should accumulate unique values across turns instead of overwriting
    LIST_FIELDS = {"materials_shared", "samples_distributed"}
    
    if intent == "LOG_INTERACTION" or state.get("interaction_status") in ["IN_PROGRESS", "READY_TO_SAVE"]:
        for key, value in entities.items():
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            # BUG-006: append-unique for list fields instead of replace
            if key in LIST_FIELDS and isinstance(value, list):
                existing = draft.get(key) or []
                merged = existing + [v for v in value if v not in existing]
                draft[key] = merged
            else:
                draft[key] = value
            
        status = "IN_PROGRESS"
    else:
        status = state.get("interaction_status") or "EMPTY"
        
    logger.info("=" * 80)
    logger.info("[MergeDraft]")
    logger.info("Draft Before Merge:")
    logger.info(json.dumps((state.get("interaction_draft") or {}), indent=2))
    logger.info("Incoming Entities:")
    logger.info(json.dumps(entities, indent=2))
    logger.info("Draft After Merge:")
    logger.info(json.dumps(draft, indent=2))
    logger.info("=" * 80)
    logger.info(f"[Node=MergeDraft] SessionId={state.get('session_id')} MergedDraftKeys={list(draft.keys())}")
    return {
        "interaction_draft": draft,
        "interaction_status": status,
        "current_node": "MergeDraft",
        "workflow_stage": "Draft Merged"
    }

def validate_draft_node(state: GraphState) -> dict:
    """
    Validates required inputs and formats, determining whether the draft is
    complete without database writes.
    
    BUG-007: Required minimum set is hcp_name + interaction_date +
    interaction_type + topics_discussed. READY_TO_SAVE only triggers when
    the interaction is meaningfully complete, not just partially filled.
    """
    draft = state.get("interaction_draft") or {}
    
    missing_fields = []
    validation_errors = []
    
    if not draft.get("hcp_name"):
        missing_fields.append("HCP Name")
    if not draft.get("interaction_date"):
        missing_fields.append("Date")
    if not draft.get("interaction_type"):
        missing_fields.append("Interaction Type")
    if not draft.get("topics_discussed"):
        missing_fields.append("Topics Discussed")
        
    idate = draft.get("interaction_date")
    if idate and not re.match(r"^\d{4}-\d{2}-\d{2}$", idate):
        validation_errors.append("Invalid date format (must be YYYY-MM-DD)")
        
    itime = draft.get("interaction_time")
    if itime and not re.match(r"^\d{2}:\d{2}$", itime):
        validation_errors.append("Invalid time format (must be HH:MM)")
        
    if not missing_fields and not validation_errors:
        status = "READY_TO_SAVE"
    else:
        status = "IN_PROGRESS"
        
    logger.info("=" * 80)
    logger.info("[ValidateDraft]")
    logger.info("Draft:")
    logger.info(json.dumps(draft, indent=2))
    logger.info(f"Missing Fields: {missing_fields}")
    logger.info(f"Validation Errors: {validation_errors}")
    logger.info(f"Interaction Status: {status}")
    logger.info("=" * 80)
    logger.info(f"[Node=ValidateDraft] SessionId={state.get('session_id')} Missing={missing_fields} Errors={validation_errors} Status={status}")
    return {
        "missing_fields": missing_fields,
        "validation_errors": validation_errors,
        "interaction_status": status,
        "current_node": "ValidateDraft",
        "workflow_stage": "Draft Validated"
    }

def generate_question_node(state: GraphState) -> dict:
    """
    Formulates a polite and context-aware follow-up question asking 
    the user for missing critical details.
    """
    draft = state.get("interaction_draft") or {}
    missing = state.get("missing_fields") or []
    last_msg = state.get("user_message") or ""
    history = state.get("conversation_history") or []
    
    prompt = QUESTION_PROMPT.format(
        draft=json.dumps(draft),
        missing_fields=", ".join(missing),
        last_user_message=last_msg,
        conversation_history=json.dumps(history[-5:])
    )
    response_obj = llm.invoke(prompt)
    response_text = response_obj.content.strip()
    
    logger.info(f"[Node=GenerateQuestion] SessionId={state.get('session_id')} Question='{response_text[:40]}...'")
    return {
        "response": response_text,
        "current_node": "GenerateQuestion",
        "workflow_stage": "Follow-Up Question Generated"
    }



def choose_tool_node(state: GraphState) -> dict:
    """
    Selects the type-safe ToolType Enum corresponding to the active intent.
    """
    intent = state.get("intent")
    tool_map = {
        "SAVE_INTERACTION": ToolType.SAVE,
        "SEARCH_HISTORY": ToolType.HISTORY,
        "GET_SUMMARY": ToolType.SUMMARY
    }
    tool = tool_map.get(intent)
    if tool is None:
        raise ValueError(f"No tool mapped for intent: {intent}")
    
    logger.info(f"[Node=ChooseTool] SessionId={state.get('session_id')} SelectedTool={tool}")
    return {
        "tool_to_execute": tool,
        "current_node": "ChooseTool",
        "workflow_stage": f"Tool Selected: {tool}"
    }

def execute_tool_node(state: GraphState) -> dict:
    """
    Dispatches database task processing to the appropriate CRM executor tool.
    """
    tool = state.get("tool_to_execute")
    draft = state.get("interaction_draft") or {}
    entities = state.get("newly_extracted_entities") or {}
    
    db = SessionLocal()
    result = {}
    error_message = None
    
    try:
        # BUG-005: lookup priority — draft first (most reliable for SAVE flow),
        # then conversation history, then message regex. Avoids unnecessary LLM calls.
        hcp_name = draft.get("hcp_name")
        if not hcp_name:
            hcp_name = entities.get("hcp_name")
        if not hcp_name:
            for turn in reversed(state.get("conversation_history") or []):
                found = turn.get("extracted_data", {}).get("hcp_name")
                if found:
                    hcp_name = found
                    break
        if not hcp_name:
            hcp_name = extract_hcp_name(state.get("user_message") or "")
        if hcp_name:
            hcp_name = normalize_hcp_name(hcp_name)

        if not hcp_name:
            raise ValueError("Doctor name is required but missing.")

        logger.info(f"[Node=ExecuteTool] SessionId={state.get('session_id')} ExecutingTool={tool} for HCP={hcp_name}")

        # Dispatch execution logic to crm_tools functions
        if tool == ToolType.SAVE:
            # BUG-004: never persist an incomplete draft. The SAVE flow bypasses
            # ValidateDraft (DetectIntent → ChooseTool), so re-apply the same
            # 4-field guard here immediately before any DB write.
            _REQUIRED = {
                "hcp_name": "HCP Name",
                "interaction_date": "Date",
                "interaction_type": "Interaction Type",
                "topics_discussed": "Topics Discussed",
            }
            missing = [label for field, label in _REQUIRED.items() if not draft.get(field)]
            if missing:
                raise ValueError(
                    f"Cannot save — missing required field(s): {', '.join(missing)}. "
                    f"Please provide these before saving."
                )
            draft = {**draft, "hcp_name": normalize_hcp_name(draft.get("hcp_name"))}
            result = execute_save(db, draft)
        elif tool == ToolType.UPDATE:
            result = execute_update(db, hcp_name, entities)
        elif tool in [ToolType.HISTORY, ToolType.SUMMARY, ToolType.NEXT_ACTION]:
            result = execute_query(db, hcp_name)
        else:
            raise ValueError(f"Unknown tool type: {tool}")
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"[Node=ExecuteTool] SessionId={state.get('session_id')} ToolExecutionFailed: {error_message}")
        db.rollback()
    finally:
        db.close()
        
    return {
        "tool_result": result,
        "error_message": error_message,
        "current_node": "ExecuteTool",
        "workflow_stage": "Tool Executed"
    }

def handle_error_node(state: GraphState) -> dict:
    """
    Formats database failure descriptions for user-friendly rendering.
    """
    err = state.get("error_message") or "An unexpected database error occurred."
    logger.warning(f"[Node=HandleError] SessionId={state.get('session_id')} Handling error: {err}")
    draft = state.get("interaction_draft") or {}
    # Preserve the draft's real lifecycle status instead of forcing READY_TO_SAVE --
    # a save can fail precisely BECAUSE the draft is incomplete (BUG-004), so
    # overwriting the status here would mask that and let a bare "save" retry
    # bypass validation again.
    if draft:
        fallback_status = state.get("interaction_status") or "IN_PROGRESS"
        if fallback_status not in ["IN_PROGRESS", "READY_TO_SAVE"]:
            fallback_status = "IN_PROGRESS"
    else:
        fallback_status = "EMPTY"
    return {
        "response": f"Error during operation: {err}",
        "interaction_status": fallback_status,
        "current_node": "HandleError",
        "workflow_stage": "Error Handled"
    }

def normalize_tool_result_node(state: GraphState) -> dict:
    """
    Standardises execution payload outputs into a uniform result schema.
    """
    result = state.get("tool_result") or {}
    normalized = {
        "hcp_name": result.get("hcp_name"),
        "status": result.get("status"),
        "interaction_id": result.get("interaction_id"),
        "history_count": len(result.get("history", [])) if "history" in result else 0
    }
    logger.info(f"[Node=NormalizeToolResult] SessionId={state.get('session_id')} NormalizedOutput={normalized}")
    return {
        "normalized_tool_result": normalized,
        "current_node": "NormalizeToolResult",
        "workflow_stage": "Tool Result Normalized"
    }

def generate_summary_node(state: GraphState) -> dict:
    """
    Uses LLM generation to write interaction logs, edit confirmation messages, 
    and relationship report text, persisting summaries to the database via CRM tools.
    """
    intent = state.get("intent")
    result = state.get("tool_result") or {}
    draft = state.get("interaction_draft") or {}
    entities = state.get("newly_extracted_entities") or {}
    
    summary_text = ""
    hcp_name = result.get("hcp_name") or draft.get("hcp_name") or entities.get("hcp_name") or "the doctor"
    
    if intent == "SAVE_INTERACTION":
        details = json.dumps(draft)
        prompt = LOG_SUMMARY_PROMPT.format(hcp_name=hcp_name, interaction_details=details)
        response_obj = llm.invoke(prompt)
        summary_text = response_obj.content.strip()
        
        # Persist summary back to DB using tool function
        int_id = result.get("interaction_id")
        if int_id:
            try:
                db_update_summary(int_id, summary_text)
                logger.info(f"[Node=GenerateSummary] SessionId={state.get('session_id')} Summary persisted for interaction={int_id}")
            except Exception as e:
                logger.error(f"[Node=GenerateSummary] Failed persisting summary: {e}")
            
    elif intent == "UPDATE_INTERACTION":
        updates = entities.get("updates") or {}
        prompt = EDIT_CONFIRMATION_PROMPT.format(hcp_name=hcp_name, updates=json.dumps(updates))
        response_obj = llm.invoke(prompt)
        summary_text = response_obj.content.strip()
        
    elif intent == "GET_SUMMARY":
        history = result.get("history") or []
        history_str = json.dumps(history)
        prompt = RELATIONSHIP_SUMMARY_PROMPT.format(hcp_name=hcp_name, history=history_str)
        response_obj = llm.invoke(prompt)
        summary_text = response_obj.content.strip()
        
    elif intent == "SEARCH_HISTORY":
        history = result.get("history") or []
        if not history:
            summary_text = f"No previous interactions found for {hcp_name}."
        else:
            lines = [f"### Interaction History for {hcp_name}"]
            for it in history:
                lines.append(f"- **{it['interaction_date']}** ({it['interaction_type']}) at {it['meeting_location'] or 'hospital'}: Topics: '{it['topics_discussed']}'. Sentiment: {it['sentiment']}.")
            summary_text = "\n".join(lines)
            
    logger.info(f"[Node=GenerateSummary] SessionId={state.get('session_id')} SummaryTextLength={len(summary_text)}")
    return {
        "summary": summary_text,
        "current_node": "GenerateSummary",
        "workflow_stage": "Summary Generated"
    }

def generate_suggestions_node(state: GraphState) -> dict:
    """
    Generates actionable rep recommendations using the LLM, 
    persisting them back to the database using CRM tool helper modules.
    """
    intent = state.get("intent")
    result = state.get("tool_result") or {}
    draft = state.get("interaction_draft") or {}
    entities = state.get("newly_extracted_entities") or {}
    
    suggestions_list = []
    
    if intent == "SAVE_INTERACTION":
        details = json.dumps(draft)
        prompt = SUGGESTION_PROMPT.format(interaction_details=details)
        response_obj = llm.invoke(prompt)
        suggestions_list = parse_json(response_obj.content)
        if not isinstance(suggestions_list, list):
            suggestions_list = []
            
        # Persist suggestions using tool function
        int_id = result.get("interaction_id")
        if int_id and suggestions_list:
            try:
                db_update_suggestions(int_id, suggestions_list)
                logger.info(f"[Node=GenerateSuggestions] SessionId={state.get('session_id')} Suggestions persisted for interaction={int_id}")
            except Exception as e:
                logger.error(f"[Node=GenerateSuggestions] Failed persisting suggestions: {e}")
    elif intent == "GET_SUMMARY":
        hcp_name = result.get("hcp_name") or draft.get("hcp_name") or entities.get("hcp_name") or "the doctor"
        history = result.get("history") or []
        prompt = NEXT_ACTION_PROMPT.format(hcp_name=hcp_name, history=json.dumps(history))
        response_obj = llm.invoke(prompt)
        suggestions_list = parse_json(response_obj.content)
        if not isinstance(suggestions_list, list):
            suggestions_list = []
            
    logger.info(f"[Node=GenerateSuggestions] SessionId={state.get('session_id')} SuggestionCount={len(suggestions_list)}")
    return {
        "suggestions": suggestions_list,
        "current_node": "GenerateSuggestions",
        "workflow_stage": "Suggestions Generated"
    }

def prepare_frontend_response_node(state: GraphState) -> dict:
    """
    Gathers variables, resets successful drafts, logs recent turns, 
    and saves the finished state back to memory.
    """
    session_id = state.get("session_id")
    user_msg = state.get("user_message") or ""
    
    response_text = state.get("response")
    if not response_text:
        summary = state.get("summary") or ""
        suggestions = state.get("suggestions") or []
        response_text = summary
        if suggestions:
            response_text += "\n\n🎯 Recommended Next Actions:\n"
            for i, s in enumerate(suggestions, 1):
                response_text += f"\n{i}. {s}"
        if not response_text:
            response_text = "Interaction processed successfully."
        
    draft = state.get("interaction_draft") or {}
    interaction_status = state.get("interaction_status") or "EMPTY"
    workflow_state = state.get("workflow_state") or "NONE"
    
    extracted_data = draft.copy()
    if not extracted_data and state.get("newly_extracted_entities"):
        extracted_data = state.get("newly_extracted_entities").copy()

    history = list(state.get("conversation_history") or [])
    if user_msg:
        history.append({
            "role": "user", 
            "content": user_msg,
            "extracted_data": extracted_data
        })
    history.append({"role": "assistant", "content": response_text})
    
    # Cap conversation history to prevent memory leaks
    history = history[-100:]
    
    updated_state = {
        **state,
        "conversation_history": history,
        "interaction_draft": draft,
        "extracted_data": extracted_data,
        "interaction_status": interaction_status,
        "workflow_state": workflow_state,
        "response": response_text,
        "interaction_complete": True,
        "current_node": "PrepareFrontendResponse",
        "workflow_stage": "Frontend Response Prepared"
    }
    
    with SESSION_LOCK:
        SESSION_STORE[session_id] = updated_state.copy()
        
    logger.info("=" * 80)
    logger.info("[PrepareFrontendResponse]")
    logger.info("Final Draft:")
    logger.info(json.dumps(updated_state["interaction_draft"], indent=2))
    logger.info("Extracted Data:")
    logger.info(json.dumps(updated_state["extracted_data"], indent=2))
    logger.info("Summary:")
    logger.info(updated_state.get("summary"))
    logger.info("Suggestions:")
    logger.info(json.dumps(updated_state.get("suggestions"), indent=2))
    logger.info("=" * 80)
    logger.info(f"[Node=PrepareFrontendResponse] SessionId={session_id} Complete=True Stage={updated_state['workflow_stage']}")
    logger.info(f"Returning Response: {updated_state['response']}")
    logger.info(f"Returning Draft: {updated_state['interaction_draft']}")
    logger.info(f"Returning Extracted Data: {updated_state['extracted_data']}")
    return updated_state

# New Node Implementations for Updates and General Chat

def retrieve_interaction_node(state: GraphState) -> dict:
    """
    Finds hcp_name from the user message, draft, or history, and retrieves
    their latest interaction record from the database.
    
    BUG-005: lookup priority is now draft → history → regex → LLM fallback.
    Draft and history are tried first as they're more reliable than regex
    (which requires the literal word 'Dr'). LLM is the last resort.
    """
    user_msg = state.get("user_message") or ""

    # 1. Draft (most reliable — already normalized on entry)
    hcp_name = (state.get("interaction_draft") or {}).get("hcp_name")

    # 2. Conversation history
    if not hcp_name:
        for turn in reversed(state.get("conversation_history") or []):
            found = turn.get("extracted_data", {}).get("hcp_name")
            if found:
                hcp_name = found
                break

    # 3. Regex extraction from current message (requires 'Dr' prefix)
    if not hcp_name:
        hcp_name = extract_hcp_name(user_msg)

    # 4. LLM fallback for bare names like "Raj Sharma" (no 'Dr' prefix)
    if not hcp_name:
        try:
            llm_response = llm.invoke(HCP_NAME_PROMPT.format(user_message=user_msg))
            llm_parsed = parse_json(llm_response.content)
            hcp_name = llm_parsed.get("hcp_name") if isinstance(llm_parsed, dict) else None
            if hcp_name:
                logger.info(f"[Node=RetrieveInteraction] HCP resolved via LLM fallback: {hcp_name}")
        except Exception as e:
            logger.warning(f"[Node=RetrieveInteraction] HCP name LLM fallback failed: {e}")

    if not hcp_name:
        return {
            "error_message": "Could not identify which doctor's interaction to update. Please mention the doctor's name.",
            "current_node": "RetrieveInteraction"
        }

    hcp_name = normalize_hcp_name(hcp_name)
        
    db = SessionLocal()
    try:
        hcp = db_search_hcp(db, hcp_name)
        if not hcp:
            return {
                "error_message": f"HCP '{hcp_name}' not found in database.",
                "current_node": "RetrieveInteraction"
            }
        latest = db.query(Interaction).filter(Interaction.hcp_id == hcp.id).order_by(
            Interaction.interaction_date.desc(),
            Interaction.created_at.desc(),
            Interaction.id.desc()
        ).first()
        
        if not latest:
            return {
                "error_message": f"No interactions found for HCP '{hcp_name}' to update.",
                "current_node": "RetrieveInteraction"
            }
            
        interaction_data = {
            "id": latest.id,
            "hcp_name": hcp.name,
            "interaction_type": latest.interaction_type,
            "interaction_date": str(latest.interaction_date) if latest.interaction_date else "",
            "interaction_time": str(latest.interaction_time) if latest.interaction_time else "",
            "meeting_location": latest.meeting_location,
            "topics_discussed": latest.topics_discussed,
            "sentiment": latest.sentiment,
            "outcomes": latest.outcomes,
            "follow_up_actions": latest.follow_up_actions,
        }
        logger.info(f"[Node=RetrieveInteraction] Found interaction: {interaction_data}")
        return {
            "newly_extracted_entities": {"hcp_name": hcp.name},
            "tool_result": interaction_data,
            "current_node": "RetrieveInteraction",
            "workflow_stage": "Interaction Retrieved"
        }
    except Exception as e:
        logger.error(f"Error retrieving interaction: {e}")
        return {
            "error_message": f"Error retrieving interaction: {str(e)}",
            "current_node": "RetrieveInteraction"
        }
    finally:
        db.close()

def extract_updates_node(state: GraphState) -> dict:
    """
    Extracts the user's requested modifications using LLM, context-aware of 
    the current retrieved database record.
    """
    error = state.get("error_message")
    if error:
        return {"current_node": "ExtractUpdates"}
        
    retrieved = state.get("tool_result") or {}
    user_msg = state.get("user_message") or ""
    
    prompt = f"""
    You are a CRM data extraction assistant.
    The user wants to update the latest interaction for the doctor {retrieved.get('hcp_name')}.
    
    Here is the current interaction details:
    {json.dumps(retrieved, indent=2)}
    
    The user request is:
    "{user_msg}"
    
    Extract the fields that need to be updated and their new values.
    Return ONLY a JSON object containing the updates.
    If a field is not mentioned to be changed, do NOT include it.
    Only include valid CRM fields:
    - interaction_type
    - interaction_date
    - interaction_time
    - meeting_location
    - attendees
    - topics_discussed
    - sentiment
    - outcomes
    - follow_up_actions
    
    Examples:
    If the user says: "He did not like Product X, change sentiment to Neutral", return:
    {{
        "sentiment": "Neutral"
    }}
    
    Return ONLY valid JSON.
    """
    
    response = llm.invoke(prompt)
    updates = parse_json(response.content)
    
    normalized_updates = updates.copy()
    if "sentiment" in normalized_updates:
        normalized_updates["sentiment"] = normalize_sentiment(normalized_updates["sentiment"])
    if "interaction_type" in normalized_updates:
        normalized_updates["interaction_type"] = normalize_interaction_type(normalized_updates["interaction_type"])
        
    logger.info(f"[Node=ExtractUpdates] Extracted updates: {normalized_updates}")
    return {
        "newly_extracted_entities": {
            "hcp_name": retrieved.get("hcp_name"),
            "updates": normalized_updates
        },
        "current_node": "ExtractUpdates",
        "workflow_stage": "Updates Extracted"
    }


def preview_changes_node(state: GraphState) -> dict:
    """
    Shows the user what changes will be applied before execution.
    """
    retrieved = state.get("tool_result") or {}
    entities = state.get("newly_extracted_entities") or {}
    updates = entities.get("updates") or {}
    hcp_name = entities.get("hcp_name") or retrieved.get("hcp_name")
    
    preview_lines = ["I found these changes:"]
    for field, new_val in updates.items():
        old_val = retrieved.get(field) or "None"
        field_title = field.replace("_", " ").title()
        preview_lines.append(f"- **{field_title}**: {old_val} ➔ {new_val}")
    preview_text = "\n".join(preview_lines)
    preview_text += "\n\nWould you like to apply these changes? (say 'yes' or 'confirm' to execute, 'no' to cancel)"
    
    # Store updates in interaction_draft so they survive across user turns
    draft_payload = {
        "hcp_name": hcp_name,
        "updates": updates
    }
    
    return {
        "response": preview_text,
        "interaction_draft": draft_payload,
        "workflow_state": "WAITING_CONFIRMATION",
        "current_node": "PreviewChanges",
        "workflow_stage": "Changes Previewed"
    }

def execute_update_node(state: GraphState) -> dict:
    """
    Applies the extracted updates directly to the database.
    """
    error = state.get("error_message")
    if error:
        return {"current_node": "ExecuteUpdate"}
        
    draft = state.get("interaction_draft") or {}
    hcp_name = draft.get("hcp_name")
    updates = draft.get("updates") or {}
    
    if not hcp_name:
        return {
            "error_message": "Doctor name missing for execution.",
            "current_node": "ExecuteUpdate"
        }
        
    entities = {
        "hcp_name": hcp_name,
        "updates": updates
    }
    
    db = SessionLocal()
    try:
        result = execute_update(db, hcp_name, entities)
        
        prompt = EDIT_CONFIRMATION_PROMPT.format(hcp_name=hcp_name, updates=json.dumps(updates))
        response_obj = llm.invoke(prompt)
        summary_text = response_obj.content.strip()
        
        return {
            "tool_result": result,
            "summary": summary_text,
            "response": summary_text,
            "interaction_draft": {},  # Clear updates from draft payload
            "workflow_state": "NONE",
            "current_node": "ExecuteUpdate",
            "workflow_stage": "Update Executed"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing update: {e}")
        return {
            "error_message": f"Error executing update: {str(e)}",
            "current_node": "ExecuteUpdate"
        }
    finally:
        db.close()

def handle_general_chat_node(state: GraphState) -> dict:
    """
    Responds to non-CRM general chat queries using the LLM.
    """
    user_msg = state.get("user_message") or ""
    history = state.get("conversation_history") or []
    
    prompt = f"""
    You are a helpful AI assistant for a Healthcare CRM.
    The medical representative might greet you, ask questions about how to use the system, or chat generally.
    Respond politely, concisely, and professionally.
    
    Conversation history:
    {json.dumps(history[-5:])}
    
    User message: "{user_msg}"
    
    Response:
    """
    response_obj = llm.invoke(prompt)
    response_text = response_obj.content.strip()
    
    return {
        "response": response_text,
        "current_node": "HandleGeneralChat",
        "workflow_stage": "General Chat Responded"
    }

def ready_to_save_response_node(state: GraphState) -> dict:
    """
    Generates the user response stating that the interaction has been captured.
    """
    return {
        "response": "I've captured the interaction. You can continue editing it or click Save Interaction whenever you're ready.",
        "current_node": "ReadyToSaveResponse",
        "workflow_stage": "Ready Response Generated"
    }

def unsaved_draft_protection_node(state: GraphState) -> dict:
    """
    Warns the user about an unsaved draft before context switching.
    """
    return {
        "response": "You have an unsaved interaction draft. Would you like to save it, discard it, or continue editing?",
        "current_node": "UnsavedDraftProtection",
        "workflow_stage": "Unsaved Draft Warning Generated"
    }

def discard_draft_node(state: GraphState) -> dict:
    """
    Clears the current interaction draft and resets to EMPTY.
    Does NOT clear the HCP name→session mapping so subsequent requests
    (history, summary, a fresh log) continue to use the same session context.
    """
    return {
        "interaction_draft": {},
        "interaction_status": "EMPTY",
        "response": "Draft discarded.",
        "current_node": "DiscardDraft",
        "workflow_stage": "Draft Discarded"
    }

def finalize_save_node(state: GraphState) -> dict:
    """
    Clears the draft and sets interaction status to SAVED.
    ONLY performs these side-effects when the current intent is SAVE_INTERACTION.
    For query flows (SEARCH_HISTORY, GET_SUMMARY) this node is a transparent
    pass-through so an in-progress draft is never silently cleared by a lookup.
    Does NOT clear the HCP name→session mapping so subsequent history/update/
    summary requests for the same doctor continue to use the same session.
    """
    intent = state.get("intent")
    if intent != "SAVE_INTERACTION":
        # Pass-through: preserve draft and its current lifecycle status
        return {
            "current_node": "FinalizeSave",
            "workflow_stage": "Save Finalized (pass-through)"
        }

    return {
        "interaction_draft": {},
        "interaction_status": "SAVED",
        "current_node": "FinalizeSave",
        "workflow_stage": "Save Finalized"
    }

def cancel_update_node(state: GraphState) -> dict:
    """
    Cancels the proposed update and resets workflow state back to NONE.
    """
    return {
        "interaction_draft": {},
        "workflow_state": "NONE",
        "response": "Update cancelled.",
        "current_node": "CancelUpdate",
        "workflow_stage": "Update Cancelled"
    }

def prompt_update_confirmation_node(state: GraphState) -> dict:
    """
    Reminds the user that confirmation is required to proceed with or cancel the updates.
    """
    return {
        "response": "Please confirm if you want to apply the updates (say 'yes' to confirm or 'no' to cancel).",
        "current_node": "PromptUpdateConfirmation",
        "workflow_stage": "Confirmation Prompted"
    }

# Graph Construction

builder = StateGraph(GraphState)

# Add Nodes
builder.add_node("LoadSession", load_session_node)
builder.add_node("InitializeRequest", initialize_request_node)
builder.add_node("ResumeDraft", resume_draft_node)
builder.add_node("RetrieveContext", retrieve_context_node)
builder.add_node("DetectIntent", detect_intent_node)
builder.add_node("ExtractJSON", extract_json_node)
builder.add_node("NormalizeFields", normalize_fields_node)
builder.add_node("MergeDraft", merge_draft_node)
builder.add_node("ValidateDraft", validate_draft_node)
builder.add_node("GenerateQuestion", generate_question_node)
builder.add_node("ChooseTool", choose_tool_node)
builder.add_node("ExecuteTool", execute_tool_node)
builder.add_node("HandleError", handle_error_node)
builder.add_node("NormalizeToolResult", normalize_tool_result_node)
builder.add_node("GenerateSummary", generate_summary_node)
builder.add_node("GenerateSuggestions", generate_suggestions_node)
builder.add_node("PrepareFrontendResponse", prepare_frontend_response_node)

# New Nodes
builder.add_node("RetrieveInteraction", retrieve_interaction_node)
builder.add_node("ExtractUpdates", extract_updates_node)
builder.add_node("PreviewChanges", preview_changes_node)
builder.add_node("ExecuteUpdate", execute_update_node)
builder.add_node("HandleGeneralChat", handle_general_chat_node)
builder.add_node("ReadyToSaveResponse", ready_to_save_response_node)
builder.add_node("UnsavedDraftProtection", unsaved_draft_protection_node)
builder.add_node("DiscardDraft", discard_draft_node)
builder.add_node("FinalizeSave", finalize_save_node)
builder.add_node("CancelUpdate", cancel_update_node)
builder.add_node("PromptUpdateConfirmation", prompt_update_confirmation_node)

# Flow Edges
builder.set_entry_point("LoadSession")
builder.add_edge("LoadSession", "InitializeRequest")
builder.add_edge("InitializeRequest", "ResumeDraft")
builder.add_edge("ResumeDraft", "RetrieveContext")
builder.add_edge("RetrieveContext", "DetectIntent")

# DetectIntent -> Route
builder.add_conditional_edges(
    "DetectIntent",
    route_after_detect_intent,
    {
        "save_flow": "ChooseTool",
        "update_flow": "RetrieveInteraction",
        "query_flow": "ChooseTool",
        "chat_flow": "HandleGeneralChat",
        "discard_flow": "DiscardDraft",
        "protection_flow": "UnsavedDraftProtection",
        "confirm_update_flow": "ExecuteUpdate",
        "cancel_update_flow": "CancelUpdate",
        "confirmation_required_flow": "PromptUpdateConfirmation",
        "logging_flow": "ExtractJSON"
    }
)

builder.add_edge("ExtractJSON", "NormalizeFields")
builder.add_edge("NormalizeFields", "MergeDraft")
builder.add_edge("MergeDraft", "ValidateDraft")

# ValidateDraft -> Route
builder.add_conditional_edges(
    "ValidateDraft",
    route_by_validation,
    {
        "incomplete": "GenerateQuestion",
        "ready": "ReadyToSaveResponse"
    }
)
builder.add_edge("ReadyToSaveResponse", "PrepareFrontendResponse")
builder.add_edge("GenerateQuestion", "PrepareFrontendResponse")

# Discard Flow Edge
builder.add_edge("DiscardDraft", "PrepareFrontendResponse")

# Protection Flow Edge
builder.add_edge("UnsavedDraftProtection", "PrepareFrontendResponse")

# General Chat Edge
builder.add_edge("HandleGeneralChat", "PrepareFrontendResponse")

# Update Flow Edges
builder.add_edge("RetrieveInteraction", "ExtractUpdates")
builder.add_edge("ExtractUpdates", "PreviewChanges")
builder.add_edge("PreviewChanges", "PrepareFrontendResponse")
builder.add_edge("ExecuteUpdate", "PrepareFrontendResponse")
builder.add_edge("CancelUpdate", "PrepareFrontendResponse")
builder.add_edge("PromptUpdateConfirmation", "PrepareFrontendResponse")

# Save and Query Flow Edges
builder.add_edge("ChooseTool", "ExecuteTool")

builder.add_conditional_edges(
    "ExecuteTool",
    route_by_tool_status,
    {
        "success": "NormalizeToolResult",
        "error": "HandleError"
    }
)

builder.add_edge("HandleError", "PrepareFrontendResponse")
builder.add_edge("NormalizeToolResult", "GenerateSummary")
builder.add_edge("GenerateSummary", "GenerateSuggestions")
builder.add_edge("GenerateSuggestions", "FinalizeSave")
builder.add_edge("FinalizeSave", "PrepareFrontendResponse")
builder.add_edge("PrepareFrontendResponse", END)

graph = builder.compile()