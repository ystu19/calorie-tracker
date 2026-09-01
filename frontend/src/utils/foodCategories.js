export const FOOD_CATEGORY_FILTERS = ["", "碳水", "蛋白质", "脂肪", "酒"];

export function foodPrimaryCategory(food) {
  const scores = [
    ["碳水", Number(food.carbs || 0)],
    ["蛋白质", Number(food.protein || 0)],
    ["脂肪", Number(food.fat || 0)],
  ];
  const primary = scores.reduce((best, current) => current[1] > best[1] ? current : best);
  return primary[1] > 0 ? primary[0] : "";
}

export function foodCategoryLabels(food) {
  const labels = [];
  const primary = foodPrimaryCategory(food);
  if (primary) labels.push(primary);
  if (Number(food.alcohol_abv || 0) > 0) labels.push("酒");
  return labels;
}

export function foodMatchesCategory(food, category) {
  if (!category) return true;
  if (category === "酒") return Number(food.alcohol_abv || 0) > 0;
  return foodPrimaryCategory(food) === category;
}
