from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FoodRecord(Base):
    __tablename__ = "food_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    food_name: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="g")
    food_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    nutrition_source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    alcohol_abv: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    meal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    eaten_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    alcohol_abv: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    base_amount: Mapped[float] = mapped_column(Float, nullable=False, default=100)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="g")
    # Legacy column names retained: values mean one common unit equals this many base units (g or ml).
    serving_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    serving_weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Legacy column retained for SQLite compatibility; application logic does not use it.
    category: Mapped[str] = mapped_column(String(20), nullable=False, server_default="综合")
    nutrition_source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)


class DailyGoal(Base):
    __tablename__ = "daily_goals"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    calories: Mapped[float] = mapped_column(Float, nullable=False, default=2000)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=120)
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=65)
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=250)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    protein_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1.2)
    fat_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    calories_goal: Mapped[float] = mapped_column(Float, nullable=False, default=1540)
    carbs_goal: Mapped[float] = mapped_column(Float, nullable=False, default=175)
    protein_goal: Mapped[float] = mapped_column(Float, nullable=False, default=84)
    fat_goal: Mapped[float] = mapped_column(Float, nullable=False, default=56)


class RecordBatchRequest(Base):
    __tablename__ = "record_batch_requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    record_ids: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
