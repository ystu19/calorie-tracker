<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import { authFetch, ensureUnlocked } from "../utils/auth.js";
import { FOOD_CATEGORY_FILTERS, foodCategoryLabels, foodMatchesCategory } from "../utils/foodCategories.js";
import { cacheKeys, deleteCachePrefix, readCache, writeFoodsCache } from "../utils/cache.js";

const allFoods = ref([]);
const category = ref("");
const search = ref("");
const loadingFoods = ref(false);
const editingId = ref(null);
const manageMode = ref(false);
const foodToDelete = ref(null);
const deletingFood = ref(false);
const saving = ref(false);
const error = ref("");
let loadRequestId = 0;
const blank = () => ({ name: "", base_amount: 100, unit: "g", common_unit: "", common_unit_amount: "", protein: "", fat: "", carbs: "", has_alcohol: false, alcohol_abv: 0, nutrition_source: "manual", estimated: false });
const form = reactive(blank());
const foods = computed(() => {
  const term = search.value.trim().toLocaleLowerCase();
  return allFoods.value.filter(food =>
    foodMatchesCategory(food, category.value) &&
    (!term || food.name.toLocaleLowerCase().includes(term))
  );
});

async function request(url, options) {
  const response = await authFetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail || "请求失败");
  }
  return response.status === 204 ? null : response.json();
}

const settled = promise => promise.then(data => ({ data }), error => ({ error }));

async function loadFoods(useCache = true) {
  const requestId = ++loadRequestId;
  loadingFoods.value = true;
  error.value = "";
  let networkResolved = false;
  const networkTask = settled(request("/api/foods?all=true&sort=usage")).then(result => {
    if (result.error) {
      if (requestId === loadRequestId) error.value = result.error.message;
      return;
    }
    if (requestId !== loadRequestId) return;
    networkResolved = true;
    allFoods.value = result.data;
    loadingFoods.value = false;
    void writeFoodsCache(result.data);
  });
  const cached = useCache ? await readCache(cacheKeys.foodsAll) : null;
  if (cached && !networkResolved && requestId === loadRequestId) {
    allFoods.value = cached;
    loadingFoods.value = false;
  }
  await networkTask;
  if (requestId === loadRequestId) loadingFoods.value = false;
}

function reset() {
  editingId.value = null;
  Object.assign(form, blank());
}

function edit(food) {
  editingId.value = food.id;
  Object.assign(form, {
    name: food.name,
    base_amount: food.base_amount,
    unit: food.unit,
    common_unit: food.common_unit || food.serving_unit || "",
    common_unit_amount: food.common_unit_amount ?? food.serving_weight_g ?? "",
    protein: food.protein,
    fat: food.fat,
    carbs: food.carbs,
    has_alcohol: Number(food.alcohol_abv) > 0,
    alcohol_abv: food.alcohol_abv || 0,
    nutrition_source: food.nutrition_source,
    estimated: food.estimated,
  });
}

async function save() {
  saving.value = true;
  error.value = "";
  try {
    await request(editingId.value ? `/api/foods/${editingId.value}` : "/api/foods", {
      method: editingId.value ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        base_amount: Number(form.base_amount),
        common_unit: form.common_unit.trim() || null,
        common_unit_amount: form.common_unit.trim() ? Number(form.common_unit_amount) : null,
        protein: Number(form.protein || 0),
        fat: Number(form.fat || 0),
        carbs: Number(form.carbs || 0),
        alcohol_abv: form.has_alcohol ? Number(form.alcohol_abv || 0) : 0,
      }),
    });
    await deleteCachePrefix("foods:");
    reset();
    await loadFoods(false);
  } catch (reason) {
    error.value = reason.message;
  } finally {
    saving.value = false;
  }
}

function remove(food) { foodToDelete.value = food; }

async function confirmRemove() {
  if (!foodToDelete.value || deletingFood.value) return;
  deletingFood.value = true;
  error.value = "";
  try {
    const food = foodToDelete.value;
    await request(`/api/foods/${food.id}`, { method: "DELETE" });
    allFoods.value = allFoods.value.filter(item => item.id !== food.id);
    if (editingId.value === food.id) reset();
    foodToDelete.value = null;
    await deleteCachePrefix("foods:");
    await loadFoods(false);
  } catch (reason) {
    error.value = `删除失败：${reason.message}`;
  } finally {
    deletingFood.value = false;
  }
}

function selectCategory(value) { category.value = value; }

watch(() => form.has_alcohol, enabled => {
  if (enabled) form.unit = "ml";
  else form.alcohol_abv = 0;
});
onMounted(() => loadFoods());

async function toggleManage() {
  if (manageMode.value) {
    manageMode.value = false;
    return;
  }
  try {
    await ensureUnlocked();
    manageMode.value = true;
  } catch {}
}
</script>
<template><section class="card food-library library-view" :class="{managing:manageMode}"><div class="section-heading"><div><p class="section-kicker">FOOD LIBRARY</p><h2>食物库</h2></div><div class="library-heading-actions"><button v-if="editingId" class="text-button" @click="reset">取消编辑</button><button class="text-button manage-button" @click="toggleManage">{{manageMode?'完成':'管理'}}</button></div></div><form class="food-form" novalidate @submit.prevent="save"><label>名称<input v-model.trim="form.name" required/></label><label>基准数量<input v-model="form.base_amount" required type="number" min="0" step="1"/></label><label>单位<select v-model="form.unit"><option>g</option><option>ml</option><option>个</option><option>份</option></select></label><label>碳水<input v-model="form.carbs" type="number" min="0" step="1"/></label><label>蛋白质<input v-model="form.protein" type="number" min="0" step="1"/></label><label>脂肪<input v-model="form.fat" type="number" min="0" step="1"/></label><label>常用单位（可选）<input v-model="form.common_unit" list="common-unit-options" maxlength="20"/><datalist id="common-unit-options"><option value="个"/><option value="片"/><option value="根"/><option value="块"/><option value="颗"/><option value="只"/><option value="份"/><option value="盒"/><option value="杯"/><option value="碗"/><option value="包"/><option value="瓶"/><option value="罐"/><option value="勺"/></datalist></label><label>每单位数量（{{form.unit}}）<input v-model="form.common_unit_amount" type="number" min="0" step="1" :required="Boolean(form.common_unit.trim())"/></label><label class="checkbox alcohol-toggle"><input v-model="form.has_alcohol" type="checkbox"/>含酒精</label><label v-if="form.has_alcohol">酒精度 %<input v-model="form.alcohol_abv" type="number" min="0" max="100" step="1"/></label><button class="primary" :disabled="saving">{{editingId?'保存食物':'加入食物库'}}</button></form><div class="category-filter library-filter"><input v-model="search" type="search" placeholder="搜索食物名称"/><button v-for="item in FOOD_CATEGORY_FILTERS" :key="item||'all'" type="button" :class="{active:category===item}" @click="selectCategory(item)">{{item||'全部'}}</button></div><p v-if="error" class="error">{{error}}</p><div v-if="foods.length" class="food-list"><article v-for="food in foods" :key="food.id" tabindex="0" @click="edit(food)" @keydown.enter="edit(food)"><div><strong>{{food.name}} <i v-if="food.estimated" class="source-tag ai_estimated">估算</i></strong><span>{{food.base_amount}}{{food.unit}}<template v-if="food.common_unit||food.serving_unit"> · 1{{food.common_unit||food.serving_unit}}={{food.common_unit_amount??food.serving_weight_g}}{{food.unit}}</template> · {{food.calories}} kcal · C {{food.carbs}} / P {{food.protein}} / F {{food.fat}} <template v-if="food.alcohol_abv>0"> · {{food.alcohol_abv}}% vol</template> · {{foodCategoryLabels(food).join(' / ')}}</span></div><div class="actions"><button class="edit" @click.stop="edit(food)">编辑</button><button class="delete" @click.stop="remove(food)">删除</button></div></article></div><p v-else-if="!error&&!loadingFoods" class="empty compact">当前分类没有食物。</p><ConfirmDialog :open="Boolean(foodToDelete)" :item-name="foodToDelete?.name||''" :loading="deletingFood" @cancel="foodToDelete=null" @confirm="confirmRemove"/></section></template>
