from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base

class Material(Base):
    __tablename__="material"
    id=Column(Integer,primary_key=True,index=True)
    interaction_id=Column(Integer,ForeignKey("interaction.id"),nullable=False)
    material_name=Column(String(150),nullable=False)
    interaction=relationship(
        "Interaction",
        back_populates="materials"
    )
