from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.card import Card
from app.models.gateway import Gateway
from app.schemas.card import CardResponse, CardUpdate
from app.models.user import User

router = APIRouter()

@router.get("/gateway/{gateway_id}", response_model=List[CardResponse])
async def get_cards_by_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    cards = db.query(Card).filter(Card.gateway_id == gateway_id).all()
    return cards

@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: int,
    card_update: CardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    
    if card_update.maintenance_mode is not None:
        card.maintenance_mode = card_update.maintenance_mode
    
    if card_update.disabled is not None:
        card.disabled = card_update.disabled
    
    db.commit()
    db.refresh(card)
    
    return card
