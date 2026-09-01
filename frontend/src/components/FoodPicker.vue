<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { FOOD_CATEGORY_FILTERS, foodPrimaryCategory } from "../utils/foodCategories.js";
import { onFoodUsageChanged } from "../utils/foodUsage.js";
import { cacheKeys, readCache, writeCache } from "../utils/cache.js";

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
const settled = promise => promise.then(data => ({ data }), error => ({ error }));

async function searchFoods(showResults = true) {
  const requestId = ++searchRequestId;
  searchController?.abort();
  searchController = new AbortController();
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams({ limit: "20", offset: "0", sort: "usage" });
  if (query.value.trim()) params.set("search", query.value.trim());
  if (category.value) params.set("primary_category", category.value);
  const key = cacheKeys.foods(params);
  let networkResolved = false;
  const networkTask = settled(fetch(`/api/foods?${params}`, { signal: searchController.signal }).then(async response => {
    if (!response.ok) throw new Error("食物搜索失败");
    return response.json();
  })).then(result => {
    if (result.error) {
      if (result.error.name !== "AbortError" && requestId === searchRequestId) {
        error.value = result.error.message || "食物搜索失败";
        if (showResults) open.value = true;
      }
      return;
    }
    if (requestId !== searchRequestId) return;
    networkResolved = true;
    results.value = result.data;
    void writeCache(key, result.data);
    if (showResults) open.value = true;
    loading.value = false;
  });
  const cached = await readCache(key);
  if (cached && !networkResolved && requestId === searchRequestId) { results.value = cached; if (showResults) open.value = true; }
  await networkTask;
  if (requestId === searchRequestId) loading.value = false;
}

function choose(food) { suppressQuerySearch = true; clearTimeout(timer); query.value = food.name; open.value = false; emit("select", food); }
function clear() { suppressQuerySearch = true; query.value = ""; emit("clear"); searchFoods(); }
function closeOnOutside(event) { if (root.value && !root.value.contains(event.target)) open.value = false; }
function closeOnEscape() { open.value = false; }
function foodCategoryShortLabel(food) { return { "碳水": "碳", "蛋白质": "蛋", "脂肪": "脂" }[foodPrimaryCategory(food)] || foodPrimaryCategory(food); }

watch(query, () => { if (suppressQuerySearch) { suppressQuerySearch = false; return; } clearTimeout(timer); timer = setTimeout(searchFoods, 180); });
watch(category, () => { clearTimeout(timer); timer = setTimeout(searchFoods, 80); });
watch(() => props.selectedId, value => { if (!value) { clearTimeout(timer); if (query.value) { suppressQuerySearch = true; query.value = ""; } open.value = false; } });
onMounted(() => { searchFoods(false); removeUsageListener = onFoodUsageChanged(() => searchFoods(false)); document.addEventListener("pointerdown", closeOnOutside); });
onBeforeUnmount(() => { clearTimeout(timer); searchController?.abort(); removeUsageListener?.(); document.removeEventListener("pointerdown", closeOnOutside); });
</script>
<template><div ref="root" class="food-picker" @keydown.esc="closeOnEscape"><div class="picker-row"><input v-model="query" :placeholder="placeholder" @pointerdown="open=true;searchFoods()"/><button v-if="selectedId" type="button" class="text-button" @click="clear">清除</button></div><div v-if="open" class="picker-results"><div class="category-filter"><button v-for="item in FOOD_CATEGORY_FILTERS" :key="item||'all'" type="button" :class="{active:category===item}" @click.stop="category=item">{{item||'全部'}}</button></div><p v-if="loading">搜索中…</p><p v-else-if="error" class="error">{{error}}</p><p v-else-if="!results.length">没有匹配食物</p><button v-for="food in results" :key="food.id" type="button" @pointerdown.prevent="choose(food)"><strong>{{food.name}}</strong><span>{{food.base_amount}}{{food.unit}} · {{food.calories}} kcal</span><small>{{foodCategoryShortLabel(food)}} · C {{food.carbs}} / P {{food.protein}} / F {{food.fat}} <template v-if="food.alcohol_abv>0">· {{food.alcohol_abv}}% vol </template><i v-if="food.estimated">估算</i></small></button></div></div></template>
