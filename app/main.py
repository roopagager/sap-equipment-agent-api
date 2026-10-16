"""FastAPI service wrapping SAP equipment data for agents and apps.

    uvicorn app.main:app --reload        # http://localhost:8000/docs
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException

from .sap_client import SapError
from .service import EquipmentService, EquipmentSummary

app = FastAPI(title="SAP Equipment API", version="1.0.0",
              description="Read-only equipment status, last maintenance and technician from SAP S/4HANA.")
_service: EquipmentService | None = None


def service() -> EquipmentService:
    global _service
    if _service is None:
        _service = EquipmentService()
    return _service


def check_key(x_api_key: str | None = Header(default=None)):
    """Optional protection for this service itself (set SERVICE_API_KEY). Not the SAP key."""
    expected = os.environ.get("SERVICE_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


@app.get("/health")
def health(svc: EquipmentService = Depends(service)):
    return {"status": "ok", "sap_mode": svc.client.mode}


@app.get("/equipment/{equipment_id}", response_model=EquipmentSummary, dependencies=[Depends(check_key)])
def get_equipment(equipment_id: str, svc: EquipmentService = Depends(service)):
    try:
        return svc.summary(equipment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SapError as e:
        raise HTTPException(status_code=502, detail=f"SAP unavailable: {e}")
