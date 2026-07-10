from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re

from ..database import SessionLocal
from ..models.interaction import Interaction
from ..models.material import Material
from ..models.sample import Sample
from ..models.ai_suggestion import AISuggestion
from ..models.hcp import HCP
from ..schemas.interaction import Interaction as InteractionSchema
from ..schemas.interaction import InteractionCreate

router = APIRouter(prefix="/interactions", tags=["interactions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_interaction_type(itype: str) -> str:
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


@router.get("/", response_model=list[InteractionSchema])
def list_interactions(db: Session = Depends(get_db)):
    return db.query(Interaction).all()


@router.get("/history/{hcp_id}", response_model=list[InteractionSchema])
def get_interaction_history(hcp_id: int, db: Session = Depends(get_db)):
    return db.query(Interaction).filter(Interaction.hcp_id == hcp_id).order_by(
        Interaction.interaction_date.desc(),
        Interaction.created_at.desc(),
        Interaction.id.desc()
    ).all()


@router.post("/", response_model=InteractionSchema)
def create_interaction(interaction: InteractionCreate, db: Session = Depends(get_db)):
    data = interaction.model_dump()
    materials_shared = data.pop("materials_shared", [])
    samples_distributed = data.pop("samples_distributed", [])
    ai_suggestions = data.pop("ai_suggestions", [])
    ai_meeting_location = data.pop("ai_meeting_location", None)

    # Normalize interaction type
    if data.get("interaction_type"):
        data["interaction_type"] = normalize_interaction_type(data["interaction_type"])

    db_interaction = Interaction(**data)
    
    # Priority for meeting location fallback:
    # 1. AI-extracted location (ai_meeting_location)
    # 2. manually entered meeting location (meeting_location)
    # 3. HCP hospital (last resort fallback)
    loc = None
    if ai_meeting_location and ai_meeting_location.strip():
        loc = ai_meeting_location.strip()
    elif data.get("meeting_location") and data.get("meeting_location").strip():
        loc = data["meeting_location"].strip()
    else:
        hcp = db.query(HCP).filter(HCP.id == db_interaction.hcp_id).first()
        if hcp:
            loc = hcp.hospital
    db_interaction.meeting_location = loc

    try:
        db.add(db_interaction)
        db.flush()

        for name in materials_shared or []:
            if name.strip():
                db.add(Material(interaction_id=db_interaction.id, material_name=name.strip()))

        for sample_str in samples_distributed or []:
            if sample_str.strip():
                name, qty = parse_sample(sample_str)
                db.add(Sample(interaction_id=db_interaction.id, sample_name=name, quantity=qty))

        for sug_text in ai_suggestions or []:
            if sug_text.strip():
                db.add(AISuggestion(interaction_id=db_interaction.id, suggestion=sug_text.strip()))

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(db_interaction)
    return db_interaction


@router.get("/{interaction_id}", response_model=InteractionSchema)
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    db_interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not db_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return db_interaction


@router.put("/{interaction_id}", response_model=InteractionSchema)
def update_interaction(interaction_id: int, interaction: InteractionCreate, db: Session = Depends(get_db)):
    db_interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not db_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
        
    data = interaction.model_dump()
    materials_shared = data.pop("materials_shared", [])
    samples_distributed = data.pop("samples_distributed", [])
    ai_suggestions = data.pop("ai_suggestions", [])
    ai_meeting_location = data.pop("ai_meeting_location", None)
    
    # Normalize interaction type
    if data.get("interaction_type"):
        data["interaction_type"] = normalize_interaction_type(data["interaction_type"])
        
    # Update core attributes
    for key, value in data.items():
        setattr(db_interaction, key, value)
        
    # Priority for meeting location fallback:
    # 1. AI-extracted location (ai_meeting_location)
    # 2. manually entered meeting location (meeting_location)
    # 3. HCP hospital (last resort fallback)
    loc = None
    if ai_meeting_location and ai_meeting_location.strip():
        loc = ai_meeting_location.strip()
    elif data.get("meeting_location") and data.get("meeting_location").strip():
        loc = data["meeting_location"].strip()
    else:
        hcp = db.query(HCP).filter(HCP.id == db_interaction.hcp_id).first()
        if hcp:
            loc = hcp.hospital
    db_interaction.meeting_location = loc

    try:
        # Child entities synchronization strategy:
        # Instead of matching existing list items and performing complex updates/diffs,
        # we perform a clean "delete-and-reinsert" strategy. This ensures that:
        # 1. Any items removed by the user in the edit form are deleted.
        # 2. Any new items added are inserted.
        # 3. Order is preserved and we avoid duplicate record issues on non-unique fields.
        # This is executed within the same database transaction, ensuring atomic safety.
        # TODO: Optimize this delete-and-reinsert strategy in the future using a diff-based synchronization algorithm.
        db.query(Material).filter(Material.interaction_id == interaction_id).delete()
        db.query(Sample).filter(Sample.interaction_id == interaction_id).delete()
        db.query(AISuggestion).filter(AISuggestion.interaction_id == interaction_id).delete()
        
        # Insert new ones
        for name in materials_shared or []:
            if name.strip():
                db.add(Material(interaction_id=db_interaction.id, material_name=name.strip()))

        for sample_str in samples_distributed or []:
            if sample_str.strip():
                name, qty = parse_sample(sample_str)
                db.add(Sample(interaction_id=db_interaction.id, sample_name=name, quantity=qty))

        for sug_text in ai_suggestions or []:
            if sug_text.strip():
                db.add(AISuggestion(interaction_id=db_interaction.id, suggestion=sug_text.strip()))

        db.commit()
    except Exception:
        db.rollback()
        raise
        
    db.refresh(db_interaction)
    return db_interaction

