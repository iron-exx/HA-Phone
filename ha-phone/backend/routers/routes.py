from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Route

router = APIRouter()


@router.get("/routes", response_model=List[Route])
def list_routes(session: Session = Depends(get_session)):
    return session.exec(select(Route)).all()


@router.post("/routes", response_model=Route)
def create_route(route: Route, session: Session = Depends(get_session)):
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


@router.patch("/routes/{route_id}", response_model=Route)
def update_route(
    route_id: int, route_data: Route, session: Session = Depends(get_session)
):
    existing = session.get(Route, route_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")
    for field, value in route_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.delete("/routes/{route_id}")
def delete_route(route_id: int, session: Session = Depends(get_session)):
    existing = session.get(Route, route_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}
