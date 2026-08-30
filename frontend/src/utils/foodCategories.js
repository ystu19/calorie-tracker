export const FOOD_CATEGORY_FILTERS = ["", "碳水", "蛋白质", "脂肪", "酒"];

export function foodPrimaryCategory(food) {
  const scores = [
    ["碳水", Number(food.carbs || 0) * 4],
    ["蛋白质", Number(food.protein || 0) * 4],
    ["脂肪", Number(food.fat || 0) * 9],
    ["酒", food.unit === "ml" ? Number(food.base_amount || 0) * Number(food.alcohol_abv || 0) / 100 * 0.789 * 7 : 0],
  ];
  const primary = scores.reduce((best, current) => current[1] > best[1] ? current : best);
  return primary[1] > 0 ? primary[0] : "";
}

export function foodCategoryLabels(food) {
  const category = foodPrimaryCategory(food);
  return category ? [category] : [];
}

export function foodMatchesCategory(food, category) {
  return !category || foodPrimaryCategory(food) === category;
}
