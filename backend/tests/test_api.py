from datetime import date, datetime, timedelta
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("EDIT_PASSWORD", "test-edit-password")

import app.main as main_module
from app.database import Base, get_db, migrate_database
from app.main import app


@pytest.fixture
def client():
    with TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine); session_factory = sessionmaker(bind=engine)
        def override_db():
            with session_factory() as db: yield db
        app.dependency_overrides[get_db] = override_db
        with TestClient(app) as test_client:
            assert test_client.post("/api/auth/unlock", json={"password": "test-edit-password"}).status_code == 200
            yield test_client
        app.dependency_overrides.clear(); engine.dispose()


def food_payload(name="测试鸡胸", unit="g", base=100, protein=30, fat=3, carbs=0, **extra):
    return {"name": name, "unit": unit, "base_amount": base, "protein": protein, "fat": fat, "carbs": carbs, **extra}


def record_payload(name="自定义", quantity=100, unit="g", protein=10, fat=2, carbs=5, **extra):
    return {"food_name": name, "quantity": quantity, "unit": unit, "protein": protein, "fat": fat, "carbs": carbs, "meal_type": "早餐", "eaten_at": datetime.now().isoformat(), **extra}


def test_write_operations_require_unlock_and_lock_revokes_cookie(client):
    assert client.post("/api/auth/lock").status_code == 200
    assert client.get("/api/foods").status_code == 200
    assert client.post("/api/foods", json=food_payload()).status_code == 401
    assert client.put("/api/settings/goals", json={"weight_kg": 70, "carbs_per_kg": 2.5, "protein_per_kg": 1.2, "fat_per_kg": 0.8}).status_code == 401
    assert client.post("/api/ai/parse", json={"text": "一个鸡蛋"}).status_code == 401
    assert client.post("/api/auth/unlock", json={"password": "wrong-password"}).status_code == 401
    unlocked = client.post("/api/auth/unlock", json={"password": "test-edit-password"})
    assert unlocked.status_code == 200
    cookie = unlocked.cookies.get("calorie_edit_session")
    assert cookie and "test-edit-password" not in cookie
    created = client.post("/api/foods", json=food_payload(name="解锁测试食物"))
    assert created.status_code == 201
    assert client.delete(f"/api/foods/{created.json()['id']}").status_code == 204
    assert client.post("/api/auth/lock").status_code == 200
    assert client.post("/api/foods", json=food_payload(name="再次锁定" )).status_code == 401


@pytest.mark.parametrize("macros,expected", [
    ({"protein": 10}, 40), ({"fat": 10}, 90), ({"protein": 10, "fat": None, "carbs": 5}, 60),
    ({"protein": 10, "fat": 2, "carbs": 5}, 78),
])
def test_macro_calorie_rules_and_empty_values(client, macros, expected):
    payload = record_payload(protein=macros.get("protein"), fat=macros.get("fat"), carbs=macros.get("carbs"))
    payload["calories"] = 9999
    result = client.post("/api/records", json=payload)
    assert result.status_code == 201
    assert result.json()["calories"] == expected
    assert result.json()["fat"] == (macros.get("fat") or 0)


@pytest.mark.parametrize("unit,base,quantity,factor", [("g", 100, 50, .5), ("个", 1, 2, 2), ("份", 1, .5, .5)])
def test_library_unit_scaling(client, unit, base, quantity, factor):
    food = client.post("/api/foods", json=food_payload(f"缩放{unit}", unit, base, 10, 2, 5)).json()
    result = client.post("/api/records", json=record_payload(food_id=food["id"], name=food["name"], unit=unit, quantity=quantity)).json()
    assert result["protein"] == 10 * factor
    assert result["fat"] == 2 * factor
    assert result["carbs"] == 5 * factor
    assert result["calories"] == 78 * factor
    assert result["nutrition_source"] == "food_library"


def test_edit_library_quantity_recalculates(client):
    food = client.post("/api/foods", json=food_payload()).json()
    created = client.post("/api/records", json=record_payload(food_id=food["id"])).json()
    update = record_payload(food_id=food["id"], quantity=50, calories=999, protein=999)
    changed = client.put(f"/api/records/{created['id']}", json=update).json()
    assert changed["protein"] == 15 and changed["calories"] == 73.5


def test_alcohol_ml_abv_calculation_and_edit(client):
    beer = client.post("/api/foods", json=food_payload("测试啤酒", unit="ml", base=500, protein=0, fat=0, carbs=0, alcohol_abv=5)).json()
    assert beer["alcohol_abv"] == 5 and beer["calories"] == 138.08
    record = client.post("/api/records", json=record_payload(name=beer["name"], food_id=beer["id"], quantity=500, unit="ml")).json()
    assert record["alcohol_abv"] == 5 and record["calories"] == 138.08
    changed = client.put(f"/api/records/{record['id']}", json=record_payload(name=beer["name"], food_id=beer["id"], quantity=1000, unit="ml")).json()
    assert changed["calories"] == 276.15


def test_food_calories_are_server_calculated_and_categories(client):
    protein = client.post("/api/foods", json={**food_payload("纯蛋白", protein=10, fat=0), "calories_per_100g": 999}).json()
    fat = client.post("/api/foods", json=food_payload("纯脂肪", protein=0, fat=10)).json()
    mixed = client.post("/api/foods", json=food_payload("均衡", protein=10, fat=0, carbs=10)).json()
    assert protein["calories"] == 40 and protein["categories"] == ["蛋白质"]
    assert fat["calories"] == 90 and fat["categories"] == ["脂肪"]
    assert set(mixed["categories"]) == {"蛋白质", "碳水"}


def test_auto_add_and_normalized_duplicate_prevention(client):
    payload = record_payload(name="  测试 米饭 ", carbs=25, protein=2, add_to_library=True)
    first = client.post("/api/records", json=payload).json()
    second = client.post("/api/records", json={**payload, "food_name": "测试米饭"}).json()
    foods = client.get("/api/foods", params={"search": "测试米饭"}).json()
    assert len(foods) == 1
    assert first["food_id"] == second["food_id"] == foods[0]["id"]


def test_ai_estimated_and_library_sources(client, monkeypatch):
    food = client.post("/api/foods", json=food_payload("米饭", carbs=25, protein=2, fat=0)).json()
    monkeypatch.setattr(main_module, "parse_food_text", lambda text, now: [
        {"food_name": "米饭", "quantity": 200, "unit": "g", "meal_type": "午餐", "eaten_at": None, "protein": 99},
        {"food_name": "未知饼", "quantity": 1, "unit": "份", "meal_type": "午餐", "eaten_at": None, "protein": 5, "fat": 2, "carbs": 20, "calories": 999},
    ])
    matched, estimated = client.post("/api/ai/parse", json={"text": "午饭"}).json()["items"]
    assert matched["food_id"] == food["id"] and matched["nutrition_source"] == "food_library"
    assert estimated["nutrition_source"] == "ai_estimated" and estimated["calories"] == 118


def test_ai_estimated_alcohol_keeps_abv_and_marker(client, monkeypatch):
    monkeypatch.setattr(main_module, "parse_food_text", lambda text, now: [{"food_name":"未知啤酒", "quantity":500, "unit":"ml", "meal_type":"晚餐", "alcohol_abv":5}])
    item = client.post("/api/ai/parse", json={"text":"喝了啤酒"}).json()["items"][0]
    assert item["nutrition_source"] == "ai_estimated"
    assert item["alcohol_abv"] == 5 and item["calories"] == 138.08


def test_ai_estimated_auto_add_keeps_estimated_marker(client):
    result = client.post("/api/records", json=record_payload(name="AI估算食物", nutrition_source="ai_estimated", add_to_library=True)).json()
    food = client.get(f"/api/foods/{result['food_id']}").json()
    assert food["estimated"] is True and food["nutrition_source"] == "ai_estimated"


def test_search_category_and_limit(client):
    for index in range(5): client.post("/api/foods", json=food_payload(f"搜索食物{index}"))
    assert len(client.get("/api/foods", params={"search": "搜索", "limit": 2}).json()) == 2
    egg = client.post("/api/foods", json=food_payload("鸡蛋", unit="个", base=1, protein=6, fat=5, carbs=.5)).json()
    protein_ids = {food["id"] for food in client.get("/api/foods", params={"category": "蛋白质"}).json()}
    fat_ids = {food["id"] for food in client.get("/api/foods", params={"category": "脂肪"}).json()}
    carbs_ids = {food["id"] for food in client.get("/api/foods", params={"category": "碳水"}).json()}
    assert set(egg["categories"]) == {"蛋白质", "脂肪", "碳水"}
    assert egg["id"] in protein_ids & fat_ids & carbs_ids


def test_old_database_migration_and_legacy_api(client):
    legacy = {"food_name": "旧接口", "weight": 80, "calories": 999, "protein": 5, "meal_type": "加餐", "eaten_at": datetime.now().isoformat()}
    result = client.post("/api/records", json=legacy)
    assert result.status_code == 201 and result.json()["quantity"] == 80 and result.json()["calories"] == 20
    with TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE food_records (id INTEGER PRIMARY KEY, food_name TEXT NOT NULL, weight REAL NOT NULL, calories REAL NOT NULL, meal_type TEXT NOT NULL, eaten_at DATETIME NOT NULL, created_at DATETIME NOT NULL)"))
            connection.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name TEXT NOT NULL, calories_per_100g REAL NOT NULL, protein_per_100g REAL NOT NULL DEFAULT 0, fat_per_100g REAL NOT NULL DEFAULT 0, carbs_per_100g REAL NOT NULL DEFAULT 0)"))
            connection.execute(text("INSERT INTO food_records VALUES (1,'旧记录',75,100,'早餐',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO foods VALUES (1,'旧食物',200,10,5,20)"))
        migrate_database(engine)
        record_cols = {c["name"] for c in inspect(engine).get_columns("food_records")}; food_cols = {c["name"] for c in inspect(engine).get_columns("foods")}
        assert {"quantity", "unit", "food_id", "nutrition_source", "alcohol_abv"} <= record_cols
        assert {"base_amount", "unit", "category", "estimated", "normalized_name", "alcohol_abv"} <= food_cols
        with engine.connect() as connection:
            assert connection.execute(text("SELECT quantity, unit FROM food_records WHERE id=1")).one() == (75, "g")
            assert connection.execute(text("SELECT base_amount, unit, normalized_name FROM foods WHERE id=1")).one() == (100, "g", "旧食物")
        engine.dispose()


def test_stats_trend_goals_and_crud(client):
    today = date.today(); yesterday = today - timedelta(days=1)
    a = client.post("/api/records", json=record_payload(eaten_at=datetime.combine(today, datetime.min.time()).isoformat())).json()
    client.post("/api/records", json=record_payload(eaten_at=datetime.combine(yesterday, datetime.min.time()).isoformat()))
    assert client.get("/api/stats/daily", params={"date": today.isoformat()}).json()["total"] == 78
    assert len(client.get("/api/stats/trend", params={"end_date": today.isoformat()}).json()) == 7
    trend_30 = client.get("/api/stats/trend", params={"end_date": today.isoformat(), "days": 30}).json()
    assert len(trend_30) == 30 and trend_30[-1]["date"] == today.isoformat()
    assert client.put("/api/settings/goals", json={"calories": 1800, "protein": 120, "fat": 60, "carbs": 200}).status_code == 200
    assert client.delete(f"/api/records/{a['id']}").status_code == 204


def test_goal_70kg_default_coefficients(client):
    result = client.put("/api/settings/goals", json={"weight_kg": 70, "carbs_per_kg": 2.5, "protein_per_kg": 1.2, "fat_per_kg": 0.8})
    assert result.status_code == 200
    body = result.json()
    assert body["carbs_goal"] == 175
    assert body["protein_goal"] == 84
    assert body["fat_goal"] == 56
    assert body["calories_goal"] == 1582.7
    assert body["calories"] == 1582.7


def test_goal_weight_and_coefficient_recalculation(client):
    first = client.put("/api/settings/goals", json={"weight_kg": 80, "carbs_per_kg": 2.5, "protein_per_kg": 1.2, "fat_per_kg": 0.8}).json()
    assert first["carbs_goal"] == 200 and first["protein_goal"] == 96 and first["fat_goal"] == 64
    changed = client.put("/api/settings/goals", json={"weight_kg": 80, "carbs_per_kg": 3, "protein_per_kg": 1.5, "fat_per_kg": 1}).json()
    assert changed["carbs_goal"] == 240 and changed["protein_goal"] == 120 and changed["fat_goal"] == 80
    assert changed["calories_goal"] == 2220


def test_goal_persistence(client):
    client.put("/api/settings/goals", json={"weight_kg": 66, "carbs_per_kg": 2.6, "protein_per_kg": 1.3, "fat_per_kg": 0.7})
    saved = client.get("/api/settings/goals").json()
    assert saved["weight_kg"] == 66 and saved["carbs_per_kg"] == 2.6
    assert saved["calories_goal"] == saved["calories"]


def test_records_persist_independently_of_query_date(client):
    today = date.today()
    dates = [today, today - timedelta(days=1), today + timedelta(days=1)]
    created = []
    for index, record_date in enumerate(dates):
        response = client.post("/api/records", json=record_payload(
            name=f"跨日期回归{index}",
            eaten_at=datetime.combine(record_date, datetime.min.time()).replace(hour=12).isoformat(),
        ))
        assert response.status_code == 201
        created.append(response.json())

    all_records = client.get("/api/records").json()
    all_ids = {record["id"] for record in all_records}
    assert {record["id"] for record in created} <= all_ids
    for record, record_date in zip(created, dates):
        dated_records = client.get("/api/records", params={"date": record_date.isoformat()}).json()
        assert record["id"] in {item["id"] for item in dated_records}


def test_legacy_goal_migration_preserves_values():
    with TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'legacy-goals.db'}")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE food_records (id INTEGER PRIMARY KEY, food_name TEXT NOT NULL, weight REAL NOT NULL, calories REAL NOT NULL, meal_type TEXT NOT NULL, eaten_at DATETIME NOT NULL, created_at DATETIME NOT NULL)"))
            connection.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name TEXT NOT NULL, calories_per_100g REAL NOT NULL, protein_per_100g REAL NOT NULL DEFAULT 0, fat_per_100g REAL NOT NULL DEFAULT 0, carbs_per_100g REAL NOT NULL DEFAULT 0)"))
            connection.execute(text("CREATE TABLE daily_goals (id INTEGER PRIMARY KEY, calories REAL NOT NULL, protein REAL NOT NULL, fat REAL NOT NULL, carbs REAL NOT NULL)"))
            connection.execute(text("INSERT INTO daily_goals VALUES (1, 1999, 101, 61, 211)"))
        migrate_database(engine)
        with engine.connect() as connection:
            row = connection.execute(text("SELECT calories_goal, protein_goal, fat_goal, carbs_goal, weight_kg FROM daily_goals WHERE id=1")).one()
        assert row == (1999, 101, 61, 211, None)
        engine.dispose()
