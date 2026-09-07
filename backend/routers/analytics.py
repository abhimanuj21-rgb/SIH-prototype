from fastapi import APIRouter
from pydantic import BaseModel

from services import feature_engineering as fe
from services import suitability as su

router = APIRouter()


class Coord(BaseModel):
    latitude: float
    longitude: float


class SuitabilityRequest(Coord):
    type: str = "agricultural"


@router.post("/features")
def features(c: Coord):
    return fe.build_feature_vector(c.latitude, c.longitude)


@router.post("/suitability")
def suitability(req: SuitabilityRequest):
    return su.assess(req.latitude, req.longitude, req.type)
