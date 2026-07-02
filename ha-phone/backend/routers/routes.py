from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Route
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


@router.get("/routes", response_model=List[Route])
def list_routes(session: Session = Depends(get_session)):
    return session.exec(select(Route)).all()


@router.post("/routes", response_model=Route)
async def create_route(route: Route, session: Session = Depends(get_session)):
    route.id = None
    session.add(route)
    session.commit()
    session.refresh(route)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return route


@router.patch("/routes/{route_id}", response_model=Route)
async def update_route(
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
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return existing


@router.delete("/routes/{route_id}")
async def delete_route(route_id: int, session: Session = Depends(get_session)):
    existing = session.get(Route, route_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")
    session.delete(existing)
    session.commit()
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return {"ok": True}
