export function getDefaultMealType(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour <= 10) return "早餐";
  if (hour >= 11 && hour <= 13) return "午餐";
  if (hour >= 14 && hour <= 16) return "加餐";
  if (hour >= 17 && hour <= 20) return "晚餐";
  return "加餐";
}
