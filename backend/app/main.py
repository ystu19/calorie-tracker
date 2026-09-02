import hashlib
import hmac
import json
import math
import os
import re
import secrets
import time as epoch_time
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_service import parse_food_text
from app.database import get_db, init_db
from app.models import DailyGoal, Food, FoodRecord, RecordBatchRequest
from app.normalization import normalize_food_name
from app.schemas import (AIParseRequest, AIParsedItem, AIParseResponse, DailyGoalResponse,
                         DailyGoalUpdate, DailyStats, FoodCreate, FoodRecordBatchCreate, FoodRecordCreate,
                         FoodRecordResponse, FoodResponse, TrendPoint, UnlockRequest)

load_dotenv()

UNITS = {"g", "ml", "个", "份"}
EDIT_COOKIE = "calorie_edit_session"
EDIT_SESSION_SECONDS = 30 * 24 * 60 * 60
UNLOCK_WINDOW_SECONDS = 60
UNLOCK_MAX_FAILURES = 5
unlock_failures: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Calorie Tracker API", version="0.4.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def edit_password() -> str:
    return os.getenv("EDIT_PASSWORD", "")


def session_signature(payload: str) -> str:
    key = hashlib.sha256((edit_password() + ":calorie-tracker-edit-session").encode()).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    payload = f"{secrets.token_urlsafe(32)}.{int(epoch_time.time()) + EDIT_SESSION_SECONDS}"
    return f"{payload}.{session_signature(payload)}"


def valid_session_token(token: str | None) -> bool:
    if not token or not edit_password(): return False
    try:
        nonce, expires, signature = token.rsplit(".", 2)
        payload = f"{nonce}.{expires}"
        return int(expires) > epoch_time.time() and hmac.compare_digest(signature, session_signature(payload))
    except (TypeError, ValueError):
        return False


@app.middleware("http")
async def require_edit_session(request: Request, call_next):
    protected = request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}
    auth_endpoint = request.url.path in {"/api/auth/unlock", "/api/auth/lock"}
    if protected and not auth_endpoint and not valid_session_token(request.cookies.get(EDIT_COOKIE)):
        return JSONResponse(status_code=401, content={"detail": "需要输入编辑密码后才能修改数据"})
    return await call_next(request)


def calories_from_macros(protein: float, fat: float, carbs: float) -> float:
    return round(protein * 4 + carbs * 4 + fat * 9, 2)


def alcohol_grams(quantity_ml: float, alcohol_abv: float) -> float:
    return quantity_ml * alcohol_abv / 100 * 0.789


def total_calories(protein: float, fat: float, carbs: float, quantity: float, unit: str, alcohol_abv: float) -> float:
    alcohol_kcal = alcohol_grams(quantity, alcohol_abv) * 7 if unit == "ml" else 0
    return round(protein * 4 + carbs * 4 + fat * 9 + alcohol_kcal, 2)


def goal_values(weight_kg: float, carbs_per_kg: float, protein_per_kg: float, fat_per_kg: float) -> dict[str, float]:
    carbs = round(weight_kg * carbs_per_kg, 2)
    protein = round(weight_kg * protein_per_kg, 2)
    fat = round(weight_kg * fat_per_kg, 2)
    calories = round(carbs * 4.1 + protein * 4.1 + fat * 9.3, 2)
    return {"carbs": carbs, "protein": protein, "fat": fat, "calories": calories}


def food_categories(protein: float, fat: float, carbs: float, alcohol_abv: float = 0) -> list[str]:
    scores = [("碳水", carbs), ("蛋白质", protein), ("脂肪", fat)]
    category, score = max(scores, key=lambda item: item[1])
    categories = [category] if score > 0 else []
    if alcohol_abv > 0: categories.append("酒")
    return categories or ["综合"]


def food_primary_category(food: Food) -> str:
    scores = [
        ("碳水", food.carbs_per_100g),
        ("蛋白质", food.protein_per_100g),
        ("脂肪", food.fat_per_100g),
    ]
    category, score = max(scores, key=lambda item: item[1])
    return category if score > 0 else ""


def day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min)
    return start, start + timedelta(days=1)


def default_meal_type(value: datetime) -> str:
    hour = value.hour
    if 5 <= hour <= 10: return "早餐"
    if 11 <= hour <= 13: return "午餐"
    if 17 <= hour <= 20: return "晚餐"
    return "加餐"


def record_for_date_statement(value: date):
    start, end = day_bounds(value)
    return select(FoodRecord).where(FoodRecord.eaten_at >= start, FoodRecord.eaten_at < end)


def get_or_404(model, item_id: int, db: Session, detail: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=detail)
    return item


def food_nutrients(payload: FoodCreate) -> tuple[float, float, float]:
    return (
        float(payload.protein if payload.protein is not None else payload.protein_per_100g or 0),
        float(payload.fat if payload.fat is not None else payload.fat_per_100g or 0),
        float(payload.carbs if payload.carbs is not None else payload.carbs_per_100g or 0),
    )


def food_to_response(food: Food) -> dict:
    return {
        "id": food.id, "name": food.name, "normalized_name": food.normalized_name,
        "base_amount": food.base_amount, "unit": food.unit,
        "serving_unit": food.serving_unit, "serving_weight_g": food.serving_weight_g,
        "calories": food.calories_per_100g, "protein": food.protein_per_100g,
        "fat": food.fat_per_100g, "carbs": food.carbs_per_100g, "alcohol_abv": food.alcohol_abv,
        "categories": food_categories(food.protein_per_100g, food.fat_per_100g, food.carbs_per_100g, food.alcohol_abv),
        "nutrition_source": food.nutrition_source, "estimated": food.estimated,
        "calories_per_100g": food.calories_per_100g, "protein_per_100g": food.protein_per_100g,
        "fat_per_100g": food.fat_per_100g, "carbs_per_100g": food.carbs_per_100g,
    }


def apply_food_payload(food: Food, payload: FoodCreate) -> None:
    protein, fat, carbs = food_nutrients(payload)
    food.name = payload.name
    food.normalized_name = normalize_food_name(payload.name)
    food.base_amount = payload.base_amount
    food.unit = payload.unit
    food.serving_unit = payload.serving_unit
    food.serving_weight_g = payload.serving_weight_g
    food.protein_per_100g = protein
    food.fat_per_100g = fat
    food.carbs_per_100g = carbs
    food.alcohol_abv = float(payload.alcohol_abv or 0)
    food.calories_per_100g = total_calories(protein, fat, carbs, food.base_amount, food.unit, food.alcohol_abv)
    food.nutrition_source = payload.nutrition_source
    food.estimated = payload.estimated or payload.nutrition_source == "ai_estimated"


def find_food_by_name(db: Session, name: str) -> Food | None:
    normalized = normalize_food_name(name)
    return db.scalar(select(Food).where(Food.normalized_name == normalized))


def food_quantity_ratio(food: Food, quantity: float, unit: str) -> tuple[float, float]:
    if food.serving_unit and unit == food.serving_unit:
        actual_weight_g = quantity * float(food.serving_weight_g or 0)
        return actual_weight_g / 100, actual_weight_g
    if unit == food.unit:
        ratio = quantity / food.base_amount
        return ratio, quantity
    supported = [food.unit]
    if food.serving_unit: supported.append(food.serving_unit)
    raise HTTPException(status_code=422, detail=f"该食物仅支持单位 {' / '.join(supported)}")


def record_values(payload: FoodRecordCreate, db: Session) -> dict:
    quantity = float(payload.quantity if payload.quantity is not None else payload.weight or 0)
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="数量必须大于 0")
    food = db.get(Food, payload.food_id) if payload.food_id else None
    if payload.food_id and food is None:
        raise HTTPException(status_code=404, detail="食物不存在")
    if food:
        ratio, actual_weight = food_quantity_ratio(food, quantity, payload.unit)
        protein = food.protein_per_100g * ratio
        fat = food.fat_per_100g * ratio
        carbs = food.carbs_per_100g * ratio
        alcohol_abv = food.alcohol_abv
        source = "food_library"
        name = food.name
    else:
        protein, fat, carbs = float(payload.protein or 0), float(payload.fat or 0), float(payload.carbs or 0)
        alcohol_abv = float(payload.alcohol_abv or 0)
        source = payload.nutrition_source if payload.nutrition_source != "food_library" else "manual"
        name = payload.food_name
        actual_weight = quantity
    values = {
        "food_name": name, "quantity": quantity, "unit": payload.unit,
        "weight": actual_weight,
        "food_id": food.id if food else None, "protein": round(protein, 2),
        "fat": round(fat, 2), "carbs": round(carbs, 2), "alcohol_abv": alcohol_abv,
        "calories": total_calories(protein, fat, carbs, quantity, payload.unit, alcohol_abv), "nutrition_source": source,
        "meal_type": payload.meal_type, "eaten_at": payload.eaten_at,
    }
    if not food and payload.add_to_library and (protein > 0 or fat > 0 or carbs > 0 or alcohol_abv > 0):
        existing = find_food_by_name(db, name)
        if existing:
            ratio, actual_weight = food_quantity_ratio(existing, quantity, payload.unit)
            values.update({
                "food_name": existing.name,
                "weight": actual_weight,
                "protein": round(existing.protein_per_100g * ratio, 2),
                "fat": round(existing.fat_per_100g * ratio, 2),
                "carbs": round(existing.carbs_per_100g * ratio, 2),
                "alcohol_abv": existing.alcohol_abv,
                "calories": total_calories(existing.protein_per_100g * ratio, existing.fat_per_100g * ratio, existing.carbs_per_100g * ratio, quantity, payload.unit, existing.alcohol_abv),
            })
            values["food_id"] = existing.id
            values["nutrition_source"] = "food_library"
        else:
            new_food = Food()
            apply_food_payload(new_food, FoodCreate(
                name=name, base_amount=quantity, unit=payload.unit, protein=protein, fat=fat, carbs=carbs, alcohol_abv=alcohol_abv,
                nutrition_source=source, estimated=source == "ai_estimated",
            ))
            db.add(new_food)
            db.flush()
            values["food_id"] = new_food.id
    return values


@app.get("/api/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict[str, bool]:
    return {"unlocked": valid_session_token(request.cookies.get(EDIT_COOKIE))}


@app.post("/api/auth/unlock")
def unlock(payload: UnlockRequest, response: Response, request: Request) -> dict[str, bool]:
    password = edit_password()
    if not password: raise HTTPException(503, "后端尚未配置 EDIT_PASSWORD")
    now = epoch_time.time(); client = request.client.host if request.client else "unknown"
    failures = [value for value in unlock_failures.get(client, []) if now - value < UNLOCK_WINDOW_SECONDS]
    if len(failures) >= UNLOCK_MAX_FAILURES:
        raise HTTPException(429, "密码尝试过于频繁，请稍后再试")
    if not hmac.compare_digest(payload.password.encode("utf-8"), password.encode("utf-8")):
        failures.append(now); unlock_failures[client] = failures
        raise HTTPException(401, "密码错误")
    unlock_failures.pop(client, None)
    response.set_cookie(
        EDIT_COOKIE, create_session_token(), max_age=EDIT_SESSION_SECONDS,
        httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}, path="/",
    )
    return {"unlocked": True}


@app.post("/api/auth/lock")
def lock(response: Response) -> dict[str, bool]:
    response.delete_cookie(EDIT_COOKIE, path="/", httponly=True, samesite="lax")
    return {"unlocked": False}


def get_daily_goal(db: Session, persist: bool = False) -> DailyGoal:
    goal = db.get(DailyGoal, 1)
    if goal is None:
        values = goal_values(70, 2.5, 1.2, 0.8)
        goal = DailyGoal(id=1, weight_kg=70, carbs_per_kg=2.5, protein_per_kg=1.2, fat_per_kg=0.8, calories=values["calories"], protein=values["protein"], fat=values["fat"], carbs=values["carbs"], calories_goal=values["calories"], protein_goal=values["protein"], fat_goal=values["fat"], carbs_goal=values["carbs"])
        if persist:
            db.add(goal); db.flush()
    elif goal.weight_kg is not None:
        values = goal_values(goal.weight_kg, goal.carbs_per_kg, goal.protein_per_kg, goal.fat_per_kg)
        if any(getattr(goal, field) != value or getattr(goal, f"{field}_goal") != value for field, value in values.items()):
            for field, value in values.items():
                setattr(goal, field, value)
                setattr(goal, f"{field}_goal", value)
            if persist:
                db.flush()
    return goal


@app.get("/api/settings/goals", response_model=DailyGoalResponse)
def read_goals(db: Session = Depends(get_db)): return get_daily_goal(db)


@app.put("/api/settings/goals", response_model=DailyGoalResponse)
def update_goals(payload: DailyGoalUpdate, db: Session = Depends(get_db)):
    goal = get_daily_goal(db, persist=True)
    if payload.weight_kg is not None:
        values = goal_values(payload.weight_kg, payload.carbs_per_kg, payload.protein_per_kg, payload.fat_per_kg)
        goal.weight_kg = payload.weight_kg
        goal.carbs_per_kg = payload.carbs_per_kg
        goal.protein_per_kg = payload.protein_per_kg
        goal.fat_per_kg = payload.fat_per_kg
        for field, value in values.items():
            setattr(goal, field, value)
            setattr(goal, f"{field}_goal", value)
    else:
        for field in ("calories", "protein", "fat", "carbs"):
            value = getattr(payload, field)
            if value is not None:
                setattr(goal, field, value)
                setattr(goal, f"{field}_goal", value)
    db.commit(); db.refresh(goal); return goal


@app.post("/api/foods", response_model=FoodResponse, status_code=201)
def create_food(payload: FoodCreate, db: Session = Depends(get_db)):
    if find_food_by_name(db, payload.name): raise HTTPException(409, "食物名称已存在")
    food = Food(); apply_food_payload(food, payload); db.add(food)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409, "食物名称已存在") from None
    db.refresh(food); return food_to_response(food)


@app.get("/api/foods", response_model=list[FoodResponse])
def list_foods(search: str | None = None, category: str | None = None, primary_category: str | None = None, sort: str | None = None, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), all_items: bool = Query(False, alias="all"), db: Session = Depends(get_db)):
    statement = select(Food)
    if search and search.strip():
        term = search.strip(); statement = statement.where(or_(Food.name.contains(term), Food.normalized_name.contains(normalize_food_name(term))))
    selected_category = primary_category or category
    if selected_category == "碳水":
        statement = statement.where(Food.carbs_per_100g > 0, Food.carbs_per_100g >= Food.protein_per_100g, Food.carbs_per_100g >= Food.fat_per_100g)
    elif selected_category == "蛋白质":
        statement = statement.where(Food.protein_per_100g > 0, Food.protein_per_100g > Food.carbs_per_100g, Food.protein_per_100g >= Food.fat_per_100g)
    elif selected_category == "脂肪":
        statement = statement.where(Food.fat_per_100g > 0, Food.fat_per_100g > Food.carbs_per_100g, Food.fat_per_100g > Food.protein_per_100g)
    elif selected_category == "酒": statement = statement.where(Food.alcohol_abv > 0)
    elif selected_category == "综合": statement = statement.where(Food.protein_per_100g == 0, Food.fat_per_100g == 0, Food.carbs_per_100g == 0, Food.alcohol_abv <= 0)
    if sort == "usage":
        cutoff = datetime.now() - timedelta(days=30)
        recent_count = func.sum(case((FoodRecord.eaten_at >= cutoff, 1), else_=0))
        last_used = func.max(FoodRecord.eaten_at)
        statement = statement.outerjoin(FoodRecord, FoodRecord.food_id == Food.id).group_by(Food.id).order_by(recent_count.desc(), last_used.desc(), Food.name)
    else:
        statement = statement.order_by(Food.name)
    if not all_items: statement = statement.offset(offset).limit(limit)
    return [food_to_response(food) for food in db.scalars(statement).all()]


@app.get("/api/foods/{food_id}", response_model=FoodResponse)
def get_food(food_id: int, db: Session = Depends(get_db)): return food_to_response(get_or_404(Food, food_id, db, "食物不存在"))


@app.put("/api/foods/{food_id}", response_model=FoodResponse)
def update_food(food_id: int, payload: FoodCreate, db: Session = Depends(get_db)):
    food = get_or_404(Food, food_id, db, "食物不存在")
    duplicate = find_food_by_name(db, payload.name)
    if duplicate and duplicate.id != food.id: raise HTTPException(409, "食物名称已存在")
    apply_food_payload(food, payload); db.commit(); db.refresh(food); return food_to_response(food)


@app.delete("/api/foods/{food_id}", status_code=204)
def delete_food(food_id: int, db: Session = Depends(get_db)):
    food = get_or_404(Food, food_id, db, "食物不存在")
    referenced_records = db.scalars(select(FoodRecord).where(FoodRecord.food_id == food_id)).all()
    for record in referenced_records:
        record.food_id = None
        record.nutrition_source = "manual"
    db.delete(food); db.commit(); return Response(status_code=204)


@app.post("/api/records", response_model=FoodRecordResponse, status_code=201)
def create_record(payload: FoodRecordCreate, db: Session = Depends(get_db)):
    record = FoodRecord(**record_values(payload, db)); db.add(record); db.commit(); db.refresh(record); return record


@app.post("/api/records/batch", response_model=list[FoodRecordResponse], status_code=201)
def create_records_batch(payload: FoodRecordBatchCreate, db: Session = Depends(get_db)):
    if payload.request_id:
        completed = db.get(RecordBatchRequest, payload.request_id)
        if completed:
            ids = json.loads(completed.record_ids)
            records_by_id = {record.id: record for record in db.scalars(select(FoodRecord).where(FoodRecord.id.in_(ids))).all()}
            return [records_by_id[item_id] for item_id in ids if item_id in records_by_id]
    records = []
    try:
        for item in payload.records:
            record = FoodRecord(**record_values(item, db))
            db.add(record)
            records.append(record)
        db.flush()
        if payload.request_id:
            db.add(RecordBatchRequest(request_id=payload.request_id, record_ids=json.dumps([record.id for record in records])))
        db.commit()
        for record in records:
            db.refresh(record)
        return records
    except Exception:
        db.rollback()
        raise


@app.get("/api/records", response_model=list[FoodRecordResponse])
def list_records(date_filter: date | None = Query(None, alias="date"), db: Session = Depends(get_db)):
    statement = select(FoodRecord) if date_filter is None else record_for_date_statement(date_filter)
    return list(db.scalars(statement.order_by(FoodRecord.eaten_at.desc(), FoodRecord.id.desc())).all())


@app.put("/api/records/{record_id}", response_model=FoodRecordResponse)
def update_record(record_id: int, payload: FoodRecordCreate, db: Session = Depends(get_db)):
    record = get_or_404(FoodRecord, record_id, db, "饮食记录不存在")
    effective = payload.model_copy(update={"food_id": record.food_id}) if record.food_id and "food_id" not in payload.model_fields_set else payload
    for field, value in record_values(effective, db).items(): setattr(record, field, value)
    db.commit(); db.refresh(record); return record


@app.delete("/api/records/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(FoodRecord, record_id, db, "饮食记录不存在")); db.commit(); return Response(status_code=204)


def ai_number(value, default: float | None = None, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return default
    try:
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
            if not match:
                return default
            value = match.group()
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None:
        number = min(number, maximum)
    return number


def ai_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def ai_unit(value) -> str:
    aliases = {"克": "g", "毫升": "ml", "个": "个", "份": "份", "g": "g", "ml": "ml"}
    normalized = str(value).strip()
    return aliases.get(normalized.lower(), normalized[:20] or "g")


@app.post("/api/ai/parse", response_model=AIParseResponse)
def ai_parse(payload: AIParseRequest, db: Session = Depends(get_db)):
    try: extracted = parse_food_text(payload.text, datetime.now())
    except RuntimeError as error: raise HTTPException(503, str(error)) from None
    except Exception: raise HTTPException(502, "AI 解析服务暂时不可用") from None
    items = []
    for raw in extracted:
        if not isinstance(raw, dict):
            continue
        try:
            raw_name = raw.get("food_name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            name = raw_name.strip(); food = find_food_by_name(db, name)
            quantity = ai_number(raw.get("quantity", raw.get("weight")), minimum=0.000001)
            unit = ai_unit(raw.get("unit") or "g")
            eaten_at = ai_datetime(raw.get("eaten_at"))
            meal_type = raw.get("meal_type") if raw.get("meal_type") in {"早餐", "午餐", "晚餐", "加餐"} else default_meal_type(eaten_at or datetime.now())
            if food:
                if unit != food.serving_unit: unit = food.unit
                ratio, actual_weight = food_quantity_ratio(food, quantity, unit) if quantity is not None else (0, 0)
                protein, fat, carbs = food.protein_per_100g * ratio, food.fat_per_100g * ratio, food.carbs_per_100g * ratio
                alcohol_abv = food.alcohol_abv
                source = "food_library"
            else:
                actual_weight = quantity if unit == "g" else None
                protein = ai_number(raw.get("protein"), default=0, minimum=0) or 0
                fat = ai_number(raw.get("fat"), default=0, minimum=0) or 0
                carbs = ai_number(raw.get("carbs"), default=0, minimum=0) or 0
                alcohol_abv = ai_number(raw.get("alcohol_abv"), default=0, minimum=0, maximum=100) or 0
                source = "ai_estimated"
            items.append(AIParsedItem(
                food_name=name, quantity=quantity, weight=actual_weight, unit=unit,
                meal_type=meal_type, eaten_at=eaten_at, matched=food is not None,
                food_id=food.id if food else None, calories=total_calories(protein, fat, carbs, quantity or 0, unit, alcohol_abv),
                protein=round(protein, 2), fat=round(fat, 2), carbs=round(carbs, 2), alcohol_abv=alcohol_abv, nutrition_source=source,
            ))
        except (TypeError, ValueError, ArithmeticError):
            continue
    return AIParseResponse(items=items)


@app.get("/api/stats/daily", response_model=DailyStats)
def daily_stats(date_filter: date = Query(alias="date"), db: Session = Depends(get_db)):
    records = list(db.scalars(record_for_date_statement(date_filter)).all()); meals = {key: 0.0 for key in ["早餐", "午餐", "晚餐", "加餐"]}
    for record in records: meals[record.meal_type] += record.calories
    return DailyStats(date=date_filter, total=sum(meals.values()), breakfast=meals["早餐"], lunch=meals["午餐"], dinner=meals["晚餐"], snack=meals["加餐"], protein=sum(r.protein for r in records), fat=sum(r.fat for r in records), carbs=sum(r.carbs for r in records))


@app.get("/api/stats/trend", response_model=list[TrendPoint])
def calorie_trend(end_date: date = Query(default_factory=date.today), days: int = Query(7, ge=1, le=31), db: Session = Depends(get_db)):
    start_date = end_date - timedelta(days=days - 1); start, _ = day_bounds(start_date); _, end = day_bounds(end_date)
    rows = db.execute(select(func.date(FoodRecord.eaten_at), func.sum(FoodRecord.calories)).where(FoodRecord.eaten_at >= start, FoodRecord.eaten_at < end).group_by(func.date(FoodRecord.eaten_at))).all()
    totals = {date.fromisoformat(day): float(total) for day, total in rows}
    return [TrendPoint(date=current, calories=totals.get(current, 0)) for offset in range(days) for current in [start_date + timedelta(days=offset)]]
