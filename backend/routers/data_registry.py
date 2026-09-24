from fastapi import APIRouter, HTTPException, Query

from services import data_registry as reg

router = APIRouter()


@router.get("/")
def list_all(status: str | None = Query(default=None),
             category: str | None = Query(default=None),
             city: str | None = Query(default=None)):
    rows = reg.list_datasets(status, category, city)
    return {"count": len(rows), "datasets": rows}


@router.get("/summary")
def registry_summary():
    return reg.summary()


@router.get("/gate/{dataset_id}")
def analytical_gate(dataset_id: str):
    if reg.get_dataset(dataset_id) is None:
        raise HTTPException(404, f"Unknown dataset '{dataset_id}'")
    return {"dataset_id": dataset_id,
            "can_use_for_analysis": reg.can_use_for_analysis(dataset_id)}


@router.get("/{dataset_id}")
def get_one(dataset_id: str):
    d = reg.get_dataset(dataset_id)
    if d is None:
        raise HTTPException(404, f"Unknown dataset '{dataset_id}'")
    return d
