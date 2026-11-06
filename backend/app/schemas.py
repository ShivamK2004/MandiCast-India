from __future__ import annotations

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    target_column: str = Field(min_length=1, max_length=255)
    date_column: str = Field(min_length=1, max_length=255)
    group_columns: list[str] = Field(default_factory=list, max_length=8)
    horizon: int = Field(default=7, ge=1, le=90)
    lookback: int = Field(default=21, ge=3, le=180)
    epochs: int = Field(default=25, ge=1, le=200)
    batch_size: int = Field(default=128, ge=8, le=2048)
    hidden_size: int = Field(default=48, ge=8, le=256)


class ApiMessage(BaseModel):
    message: str
