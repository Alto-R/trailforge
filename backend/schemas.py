"""Pydantic request/response models for the exploration-aid API (设计 R1.3).

Pure contract definitions — no runtime artifacts imported.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PersonaOut(BaseModel):
    """One onboarding persona (a GMM profile group), for GET /personas."""
    id: str = Field(..., examples=["c0"])
    label: str = Field(..., description="short display name (human-refined draft)")
    description: str
    size: int = Field(..., ge=0)
    default_prefs: dict[str, float] = Field(
        default_factory=dict, description="default preference weights for this persona")


class RouteRequest(BaseModel):
    """POST /route: where to start, who/what the user likes, how far, how many."""
    start: tuple[float, float] = Field(..., description="[lng, lat] WGS84 start click")
    persona: str | None = Field(None, description="persona id -> default preferences")
    preferences: dict[str, float] | None = Field(
        None, description="explicit preference weights; overrides persona defaults",
        examples=[{"challenge": 1.0, "scenic": 0.5}])
    budget_km: float = Field(..., gt=0, le=50, description="target route length (km)")
    n_routes: int = Field(4, ge=1, le=8, description="how many candidates to return")
    loop: bool = Field(False, description="T2.6: generate loop routes that return to the start")

    @property
    def lng(self) -> float:
        return self.start[0]

    @property
    def lat(self) -> float:
        return self.start[1]


class RouteCandidate(BaseModel):
    """One recommended route in the candidate list."""
    length_km: float
    n_segments: int
    reachable: bool
    score: float = Field(..., description="relevance (mean segment score along route)")
    segments: list[int]
    geojson: dict = Field(..., description="FeatureCollection of the route, WGS84")
    attributes: dict = Field(default_factory=dict, description="mean attrs along route")
    labels: list[str] = Field(default_factory=list, description="explainable why-tags")
    loop: bool = Field(False, description="T2.6: True if this is a loop route")
    closed: bool = Field(False, description="T2.6: True if the loop returns by a mostly-new path (a real loop, not a retrace)")


class RouteResponse(BaseModel):
    """POST /route: ranked, MMR-diversified candidate routes."""
    candidates: list[RouteCandidate]
    start_snapped: tuple[float, float] = Field(..., description="[lng, lat] snapped start")
    reachable: bool = Field(..., description="False if no candidate reached the budget")
    prefs_used: dict[str, float] = Field(default_factory=dict)
    note: str | None = Field(None, description="e.g. 'area supports only ~1.2km'")


class HealthOut(BaseModel):
    status: str = "ok"
    model_loaded: bool
    n_segments: int
    n_personas: int


class FeedbackIn(BaseModel):
    """POST /feedback: minimal Module E — which candidate chosen + a rating."""
    chosen_index: int | None = Field(None, ge=0, description="index into the candidate list")
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None
    context: dict | None = Field(None, description="optional echo of the route request")


class FeedbackOut(BaseModel):
    status: str = "ok"
    stored: int = Field(..., description="total feedback records so far")
