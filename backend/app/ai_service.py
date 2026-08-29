import json
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def parse_food_text(text: str, now: datetime) -> list[dict]:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 或 OPENAI_API_KEY 未配置")

    client_options = {"api_key": api_key}
    base_url = os.getenv("AI_BASE_URL")
    if base_url:
        client_options["base_url"] = base_url

    client = OpenAI(**client_options)
    model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    system_prompt = (
        "你是饮食记录解析器。请只输出 JSON，不要输出 Markdown。"
        "JSON 格式必须是：{\"items\":[{\"food_name\":\"食物名\","
        "\"quantity\":数量或null,\"unit\":\"g/ml/个/份\",\"meal_type\":\"早餐/午餐/晚餐/加餐\","
        "\"eaten_at\":ISO 8601时间或null,\"protein\":估算克数,\"fat\":估算克数,"
        "\"carbs\":估算克数,\"alcohol_abv\":酒精度百分比或0,\"calories\":估算千卡}]}。"
        "提取用户明确提到的食物、数量、单位、餐次和时间。可根据常见食物份量估算营养；"
        "酒类数量优先使用 ml，并估算 alcohol_abv；无法确定数量时 quantity 返回 null。一个/一份分别使用个/份。早饭映射早餐，午饭映射午餐，晚饭映射晚餐，"
        "其余映射加餐。"
        f"当前本地时间是 {now.isoformat()}；若只有时间没有日期，使用今天。"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        max_tokens=1200,
        stream=False,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("AI 服务返回了空内容，请重试")
    result = json.loads(content)
    if not isinstance(result.get("items"), list):
        raise RuntimeError("AI 服务返回格式不正确")
    return result["items"]
