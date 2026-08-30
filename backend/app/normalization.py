import re


def normalize_food_name(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.strip().casefold(), flags=re.UNICODE)
