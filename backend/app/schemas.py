from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MealType = Literal["早餐", "午餐", "晚餐", "加餐"]
FoodUnit = Literal["g", "ml", "个", "份"]
NutritionSource = Literal["manual", "food_library", "ai_estimated"]
FoodCategory = Literal["碳水", "蛋白质", "脂肪", "酒", "综合"]


class UnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class FoodRecordCreate(BaseModel):
    food_name: str = Field(min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0)
    unit: FoodUnit = "g"
    food_id: int | None = None
    weight: float | None = Field(default=None, gt=0)
    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=0, ge=0)
    fat: float | None = Field(default=0, ge=0)
    carbs: float | None = Field(default=0, ge=0)
    alcohol_abv: float | None = Field(default=0, ge=0, le=100)
    nutrition_source: NutritionSource = "manual"
    add_to_library: bool = False
    meal_type: MealType
    eaten_at: datetime

    @field_validator("food_name")
    @classmethod
    def strip_food_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("食物名称不能为空")
        return value


class FoodRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    food_name: str
    quantity: float
    unit: FoodUnit
    food_id: int | None
    weight: float
    calories: float
    protein: float
    fat: float
    carbs: float
    alcohol_abv: float
    nutrition_source: NutritionSource
    meal_type: MealType
    eaten_at: datetime
    created_at: datetime


class FoodRecordBatchCreate(BaseModel):
    records: list[FoodRecordCreate] = Field(min_length=1, max_length=50)


class FoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_amount: float = Field(default=100, gt=0)
    unit: FoodUnit = "g"
    protein: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    alcohol_abv: float | None = Field(default=0, ge=0, le=100)
    nutrition_source: NutritionSource = "manual"
    estimated: bool = False
    # Legacy request fields remain accepted. calories_per_100g is ignored.
    calories_per_100g: float | None = Field(default=None, ge=0)
    protein_per_100g: float | None = Field(default=None, ge=0)
    fat_per_100g: float | None = Field(default=None, ge=0)
    carbs_per_100g: float | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("食物名称不能为空")
        return value


class FoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    normalized_name: str
    base_amount: float
    unit: FoodUnit
    calories: float
    protein: float
    fat: float
    carbs: float
    alcohol_abv: float
    categories: list[FoodCategory]
    nutrition_source: NutritionSource
    estimated: bool
    calories_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float


class DailyStats(BaseModel):
    date: date
    total: float
    breakfast: float
    lunch: float
    dinner: float
    snack: float
    protein: float
    fat: float
    carbs: float


class TrendPoint(BaseModel):
    date: date
    calories: float


class DailyGoalUpdate(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0)
    carbs_per_kg: float = Field(default=2.5, gt=0)
    protein_per_kg: float = Field(default=1.2, gt=0)
    fat_per_kg: float = Field(default=0.8, gt=0)
    # Legacy clients may still submit direct goals when no weight is provided.
    calories: float | None = Field(default=None, gt=0)
    protein: float | None = Field(default=None, gt=0)
    fat: float | None = Field(default=None, gt=0)
    carbs: float | None = Field(default=None, gt=0)


class DailyGoalResponse(DailyGoalUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    calories: float
    protein: float
    fat: float
    carbs: float
    calories_goal: float
    protein_goal: float
    fat_goal: float
    carbs_goal: float


class AIParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class AIParsedItem(BaseModel):
    food_name: str
    quantity: float | None
    unit: FoodUnit
    weight: float | None = None
    meal_type: MealType
    eaten_at: datetime | None
    matched: bool
    food_id: int | None = None
    calories: float | None = None
    protein: float | None = None
    fat: float | None = None
    carbs: float | None = None
    alcohol_abv: float | None = Field(default=0, ge=0, le=100)
    nutrition_source: NutritionSource


class AIParseResponse(BaseModel):
    items: list[AIParsedItem]
