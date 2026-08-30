<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { FOOD_CATEGORY_FILTERS, foodCategoryLabels } from "../utils/foodCategories.js";
import { onFoodUsageChanged } from "../utils/foodUsage.js";

const props = defineProps({ selectedId: { type: [Number, String], default: "" }, placeholder: { type: String, default: "搜索食物名称" } });
const emit = defineEmits(["select", "clear"]);
const query = ref("");
const category = ref("");
const results = ref([]);
const open = ref(false);
const loading = ref(false);
const error = ref("");
const root = ref(null);
let timer, searchController, removeUsageListener;
let suppressQuerySearch = false;
let searchRequestId = 0;

async function searchFoods(showResults = true) {
  const requestId = ++searchRequestId;
  searchController?.abort();
  searchController = new AbortController();
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams({ limit: "20", offset: "0", sort: "usage" });
  if (query.value.trim()) params.set("search", query.value.trim());
  if (category.value) params.set("primary_category", category.value);
  try {
    const response = await fetch(`/api/foods?${params}`, { signal: searchController.signal });
    if (!response.ok) throw new Error("食物搜索失败");
    const foods = await response.json();
    if (requestId !== searchRequestId) return;
    results.value = foods;
    if (showResults) open.value = true;
  } catch (reason) {
    if (reason.name !== "AbortError" && requestId === searchRequestId) {
      results.value = [];
      error.value = reason.message || "食物搜索失败";
      if (showResults) open.value = true;
    }
  } finally {
    if (requestId === searchRequestId) loading.value = false;
  }
}

function choose(food) { suppressQuerySearch = true; clearTimeout(timer); query.value = food.name; open.value = false; emit("select", food); }
function clear() { suppressQuerySearch = true; query.value = ""; emit("clear"); searchFoods(); }
function closeOnOutside(event) { if (root.value && !root.value.contains(event.target)) open.value = false; }
function closeOnEscape() { open.value = false; }

watch(query, () => { if (suppressQuerySearch) { suppressQuerySearch = false; return; } clearTimeout(timer); timer = setTimeout(searchFoods, 180); });
watch(category, () => { clearTimeout(timer); timer = setTimeout(searchFoods, 80); });
watch(() => props.selectedId, value => { if (!value) { clearTimeout(timer); if (query.value) { suppressQuerySearch = true; query.value = ""; } open.value = false; } });
onMounted(() => { searchFoods(false); removeUsageListener = onFoodUsageChanged(() => searchFoods(false)); document.addEventListener("pointerdown", closeOnOutside); });
onBeforeUnmount(() => { clearTimeout(timer); searchController?.abort(); removeUsageListener?.(); document.removeEventListener("pointerdown", closeOnOutside); });
</script>
<template><div ref="root" class="food-picker" @keydown.esc="closeOnEscape"><div class="picker-row"><input v-model="query" :placeholder="placeholder" @pointerdown="open=true;searchFoods()"/><button v-if="selectedId" type="button" class="text-button" @click="clear">清除</button></div><div v-if="open" class="picker-results"><div class="category-filter"><button v-for="item in FOOD_CATEGORY_FILTERS" :key="item||'all'" type="button" :class="{active:category===item}" @click.stop="category=item">{{item||'全部'}}</button></div><p v-if="loading">搜索中…</p><p v-else-if="error" class="error">{{error}}</p><p v-else-if="!results.length">没有匹配食物</p><button v-for="food in results" :key="food.id" type="button" @pointerdown.prevent="choose(food)"><strong>{{food.name}}</strong><span>{{food.base_amount}}{{food.unit}} · {{food.calories}} kcal</span><small>{{foodCategoryLabels(food).join(' / ')}} · C {{food.carbs}} / P {{food.protein}} / F {{food.fat}} <template v-if="food.alcohol_abv>0">· {{food.alcohol_abv}}% vol </template><i v-if="food.estimated">估算</i></small></button></div></div></template>
