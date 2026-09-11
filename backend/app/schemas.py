from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

MealType = Literal["早餐", "午餐", "晚餐", "加餐"]
FoodUnit = Literal["g", "ml", "个", "份"]
NutritionSource = Literal["manual", "food_library", "ai_estimated"]
FoodCategory = Literal["碳水", "蛋白质", "脂肪", "酒", "综合"]


class UnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class FoodRecordCreate(BaseModel):
    food_name: str = Field(min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0)
    unit: str = Field(default="g", min_length=1, max_length=20)
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
    unit: str
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
    request_id: str | None = Field(default=None, min_length=8, max_length=64)


class FoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_amount: float = Field(default=100, gt=0)
    unit: FoodUnit = "g"
    common_unit: str | None = Field(default=None, max_length=20, validation_alias=AliasChoices("common_unit", "serving_unit"))
    common_unit_amount: float | None = Field(default=None, gt=0, validation_alias=AliasChoices("common_unit_amount", "serving_weight_g"))
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

    @field_validator("common_unit", mode="before")
    @classmethod
    def normalize_serving_unit(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @model_validator(mode="after")
    def validate_serving(self):
        if self.common_unit and self.common_unit_amount is None:
            raise ValueError("填写常用单位时，每单位数量必须大于 0")
        if not self.common_unit and self.common_unit_amount is not None:
            raise ValueError("填写每单位数量时，必须同时填写常用单位")
        if self.common_unit and self.unit not in {"g", "ml"}:
            raise ValueError("常用单位换算仅适用于基础单位为 g 或 ml 的食物")
        if self.common_unit and self.base_amount != 100:
            raise ValueError("配置常用单位时，基准数量必须为 100")
        if self.common_unit == self.unit:
            raise ValueError("常用单位不能与基础单位相同")
        return self


class FoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    normalized_name: str
    base_amount: float
    unit: FoodUnit
    common_unit: str | None
    common_unit_amount: float | None
    # Legacy response fields retained for existing clients and stored SQLite columns.
    serving_unit: str | None
    serving_weight_g: float | None
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
    unit: str = Field(min_length=1, max_length=20)
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
