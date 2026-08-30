const FOOD_USAGE_CHANGED = "calorie-food-usage-changed";

export function notifyFoodUsageChanged() {
  window.dispatchEvent(new Event(FOOD_USAGE_CHANGED));
}

export function onFoodUsageChanged(handler) {
  window.addEventListener(FOOD_USAGE_CHANGED, handler);
  return () => window.removeEventListener(FOOD_USAGE_CHANGED, handler);
}
