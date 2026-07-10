from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from ..database import Base

class AISuggestion(Base):
    __tablename__="ai_suggestion"
    id=Column(Integer,primary_key=True,index=True)
    interaction_id=Column(Integer,ForeignKey("interaction.id"),nullable=False)
    suggestion=Column(Text,nullable=False)
    interaction=relationship(
        "Interaction",
        back_populates="ai_suggestions"
    )