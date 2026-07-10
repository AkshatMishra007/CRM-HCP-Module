from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base

class HCP(Base):
    __tablename__="hcp"
    id=Column(Integer,primary_key=True,index=True)
    name=Column(String(100),nullable=False)
    hospital=Column(String(150),nullable=False)
    specialization=Column(String(100))
    city=Column(String(100))
    created_at=Column(DateTime(
        timezone=True),
        server_default=func.now()
    )

    interactions=relationship(
        "Interaction",
        back_populates="hcp",
        cascade="all, delete-orphan"
    )

    