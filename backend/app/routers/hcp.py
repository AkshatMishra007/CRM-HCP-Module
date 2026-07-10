from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..database import SessionLocal
from ..models.hcp import HCP
from ..schemas.hcp import HCP as HCPSchema
from ..schemas.hcp import  HCPCreate, HCPUpdate
router = APIRouter(prefix="/hcps", tags=["hcps"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get("/", response_model=list[HCPSchema])
def list_hcps(db: Session = Depends(get_db)):
    return db.query(HCP).all()


@router.get("/search", response_model=list[HCPSchema])
def search_hcps(q: str = "", db: Session = Depends(get_db)):
    if not q:
        return db.query(HCP).all()
    return db.query(HCP).filter(
        (HCP.name.ilike(f"%{q}%")) |
        (HCP.hospital.ilike(f"%{q}%")) |
        (HCP.specialization.ilike(f"%{q}%"))
    ).all()


@router.post("/", response_model=HCPSchema)
def create_hcp(hcp: HCPCreate, db: Session = Depends(get_db)):
    db_hcp = HCP(**hcp.model_dump())
    db.add(db_hcp)
    db.commit()
    db.refresh(db_hcp)
    return db_hcp
@router.put("/{hcp_id}", response_model=HCPSchema)
def update_hcp(
    hcp_id: int,
    payload: HCPUpdate,
    db: Session = Depends(get_db),
):
    hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
    if not hcp:
        raise HTTPException(status_code=404, detail="HCP not found")

    if payload.name:
        hcp.name = payload.name

    if payload.hospital:
        hcp.hospital = payload.hospital

    if payload.specialization:
        hcp.specialization = payload.specialization

    if payload.city:
        hcp.city = payload.city

    db.commit()
    db.refresh(hcp)

    return hcp