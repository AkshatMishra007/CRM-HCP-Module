from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base

class Sample(Base):
    __tablename__="sample"
    id=Column(Integer,primary_key=True,index=True)
    interaction_id=Column(
        Integer,
        ForeignKey("interaction.id"),
        nullable=False
    )
    sample_name=Column(String(150),nullable=False)
    
    quantity=Column(
        Integer,
        nullable=False
    )
    interaction=relationship(
        "Interaction",
        back_populates="samples"
    )