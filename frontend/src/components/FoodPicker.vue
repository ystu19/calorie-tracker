<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { FOOD_CATEGORY_FILTERS, foodMatchesCategory, foodPrimaryCategory } from "../utils/foodCategories.js";
import { onFoodUsageChanged } from "../utils/foodUsage.js";
import { cacheKeys, readCache, writeFoodsCache } from "../utils/cache.js";

const props = defineProps({ selectedId: { type: [Number, String], default: "" }, placeholder: { type: String, default: "搜索食物名称" } });
const emit = defineEmits(["select", "clear"]);
const query = ref("");
const category = ref("");
const allFoods = ref([]);
const open = ref(false);
const loading = ref(false);
const error = ref("");
const root = ref(null);
let removeUsageListener;
let loadRequestId = 0;
let touchStartX = 0;
let touchStartY = 0;
let touchMoved = false;
let ignoreClickUntil = 0;
const settled = promise => promise.then(data => ({ data }), error => ({ error }));
const results = computed(() => {
  const term = query.value.trim().toLocaleLowerCase();
  return allFoods.value.filter(food =>
    foodMatchesCategory(food, category.value) &&
    (!term || food.name.toLocaleLowerCase().includes(term))
  );
});

async function loadFoods(showResults = false, useCache = true) {
  const requestId = ++loadRequestId;
  loading.value = true;
  error.value = "";
  let networkResolved = false;
  const networkTask = settled(fetch("/api/foods?all=true&sort=usage").then(async response => {
    if (!response.ok) throw new Error("食物列表加载失败");
    return response.json();
  })).then(result => {
    if (result.error) {
      if (requestId === loadRequestId) {
        error.value = result.error.message || "食物列表加载失败";
        if (showResults) open.value = true;
      }
      return;
    }
    if (requestId !== loadRequestId) return;
    networkResolved = true;
    allFoods.value = result.data;
    void writeFoodsCache(result.data);
    if (showResults) open.value = true;
    loading.value = false;
  });
  const cached = useCache ? await readCache(cacheKeys.foodsAll) : null;
  if (cached && !networkResolved && requestId === loadRequestId) {
    allFoods.value = cached;
    if (showResults) open.value = true;
    loading.value = false;
  }
  await networkTask;
  if (requestId === loadRequestId) loading.value = false;
}

function choose(food) {
  query.value = food.name;
  open.value = false;
  emit("select", food);
}
function startTouch(event) {
  const touch = event.touches[0];
  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
  touchMoved = false;
}
function moveTouch(event) {
  const touch = event.touches[0];
  if (Math.hypot(touch.clientX - touchStartX, touch.clientY - touchStartY) > 8) touchMoved = true;
}
function finishInputTouch() {
  ignoreClickUntil = Date.now() + 500;
  if (!touchMoved) open.value = true;
}
function finishFoodTouch(food) {
  ignoreClickUntil = Date.now() + 500;
  if (!touchMoved) choose(food);
}
function openFromClick() { if (Date.now() >= ignoreClickUntil) open.value = true; }
function chooseFromClick(food) { if (Date.now() >= ignoreClickUntil) choose(food); }
function clear() {
  query.value = "";
  emit("clear");
}
function closeOnOutside(event) { if (root.value && !root.value.contains(event.target)) open.value = false; }
function closeOnEscape() { open.value = false; }
function foodCategoryShortLabel(food) { if (Number(food.alcohol_abv) > 0) return "酒"; return { "碳水": "碳", "蛋白质": "蛋", "脂肪": "脂" }[foodPrimaryCategory(food)] || foodPrimaryCategory(food); }

watch(() => props.selectedId, value => {
  if (!value) {
    if (query.value) query.value = "";
    open.value = false;
  }
});
onMounted(() => {
  loadFoods();
  removeUsageListener = onFoodUsageChanged(() => loadFoods(false, false));
  document.addEventListener("pointerdown", closeOnOutside);
});
onBeforeUnmount(() => {
  removeUsageListener?.();
  document.removeEventListener("pointerdown", closeOnOutside);
});
</script>
<template><div ref="root" class="food-picker" @keydown.esc="closeOnEscape"><div class="picker-row"><input v-model="query" :placeholder="placeholder" @click="openFromClick" @touchstart.passive="startTouch" @touchmove.passive="moveTouch" @touchend="finishInputTouch"/><button v-if="selectedId" type="button" class="text-button" @click="clear">清除</button></div><div v-if="open" class="picker-results"><div class="category-filter"><button v-for="item in FOOD_CATEGORY_FILTERS" :key="item||'all'" type="button" :class="{active:category===item}" @click.stop="category=item">{{item||'全部'}}</button></div><p v-if="loading">加载中…</p><p v-else-if="error" class="error">{{error}}</p><p v-else-if="!results.length">没有匹配食物</p><button v-for="food in results" :key="food.id" type="button" @click="chooseFromClick(food)" @touchstart.passive="startTouch" @touchmove.passive="moveTouch" @touchend="finishFoodTouch(food)"><strong>{{food.name}}</strong><span>{{food.base_amount}}{{food.unit}}<template v-if="food.common_unit||food.serving_unit"> · 1{{food.common_unit||food.serving_unit}}={{food.common_unit_amount??food.serving_weight_g}}{{food.unit}}</template> · {{Math.round(food.calories)}} kcal</span><small>{{foodCategoryShortLabel(food)}} · C {{food.carbs}} / P {{food.protein}} / F {{food.fat}} <template v-if="food.alcohol_abv>0">· {{food.alcohol_abv}}% vol </template><i v-if="food.estimated">估算</i></small></button></div></div></template>
