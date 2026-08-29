export const FOOD_CATEGORY_FILTERS = ["", "碳水", "蛋白质", "脂肪", "酒"];

export function foodCategoryLabels(food) {
  if (Array.isArray(food.categories)) return food.categories;
  const labels = [];
  if (Number(food.carbs) > 0) labels.push("碳水");
  if (Number(food.protein) > 0) labels.push("蛋白质");
  if (Number(food.fat) > 0) labels.push("脂肪");
  if (Number(food.alcohol_abv) > 0) labels.push("酒");
  return labels;
}
