import logging
from app.agent.state import GraphState

logger = logging.getLogger("hcp_crm_graph")

def route_after_detect_intent(state: GraphState) -> str:
    """
    Determines the path after identifying user intent.
    """
    intent = state.get("intent") or "LOG_INTERACTION"
    logger.info(f"[Router] route_after_detect_intent -> intent={intent}")
    
    if intent == "SAVE_INTERACTION":
        return "save_flow"
    elif intent == "UPDATE_INTERACTION":
        return "update_flow"
    elif intent in ["SEARCH_HISTORY", "GET_SUMMARY"]:
        return "query_flow"
    elif intent == "GENERAL_CHAT":
        return "chat_flow"
    elif intent == "CONFIRM_UPDATE":
        return "confirm_update_flow"
    elif intent == "CANCEL_UPDATE":
        return "cancel_update_flow"
    elif intent == "DISCARD_DRAFT":
        return "discard_flow"
    elif intent == "UNSAVED_DRAFT_PROTECTION":
        return "protection_flow"
    else:
        return "logging_flow"

def route_by_validation(state: GraphState) -> str:
    """
    Decides whether to ask follow-up questions for missing fields
    or complete the log step and wait for explicit save.
    """
    status = state.get("interaction_status")
    
    missing = state.get("missing_fields")
    errors = state.get("validation_errors")
    if (missing and len(missing) > 0) or (errors and len(errors) > 0):
        logger.info(f"[Router] route_by_validation -> incomplete (missing={missing}, errors={errors})")
        return "incomplete"
        
    logger.info(f"[Router] route_by_validation -> ready")
    return "ready"

def route_by_tool_status(state: GraphState) -> str:
    """
    Decides between the error handler or standard success workflow.
    """
    if state.get("error_message"):
        logger.info(f"[Router] route_by_tool_status -> error (error_message={state.get('error_message')})")
        return "error"
    logger.info("[Router] route_by_tool_status -> success")
    return "success"


