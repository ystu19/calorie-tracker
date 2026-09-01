<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { authFetch } from "../utils/auth.js";
import { cacheKeys, readCache, writeCache } from "../utils/cache.js";

const emit = defineEmits(["saved"]);
const form = reactive({ weight_kg: "", carbs_per_kg: 2.5, protein_per_kg: 1.2, fat_per_kg: 0.8, calories: 2000, protein: 120, fat: 65, carbs: 250 });
const saving = ref(false), message = ref("");
let active = true;
const settled = promise => promise.then(data => ({ data }), error => ({ error }));
const round = value => Math.round((Number(value) + Number.EPSILON) * 100) / 100;
const preview = computed(() => {
  const weight = Number(form.weight_kg);
  if (!weight) return { calories: form.calories, protein: form.protein, fat: form.fat, carbs: form.carbs };
  const carbs = round(weight * Number(form.carbs_per_kg));
  const protein = round(weight * Number(form.protein_per_kg));
  const fat = round(weight * Number(form.fat_per_kg));
  return { carbs, protein, fat, calories: round(carbs * 4.1 + protein * 4.1 + fat * 9.3) };
});

onMounted(async () => {
  let networkResolved = false;
  const networkTask = settled(fetch("/api/settings/goals")).then(async result => {
    if (!active) return;
    if (result.error) { message.value = result.error.message || "目标加载失败"; return; }
    if (!result.data.ok) { message.value = "目标加载失败"; return; }
    const goals = await result.data.json();
    if (!active) return;
    networkResolved = true; Object.assign(form, goals); void writeCache(cacheKeys.goals, goals);
  });
  const cached = await readCache(cacheKeys.goals);
  if (cached && !networkResolved && active) Object.assign(form, cached);
  await networkTask;
});
onBeforeUnmount(() => { active = false; });
async function save() {
  saving.value = true; message.value = "";
  try {
    const response = await authFetch("/api/settings/goals", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ weight_kg:Number(form.weight_kg), carbs_per_kg:Number(form.carbs_per_kg), protein_per_kg:Number(form.protein_per_kg), fat_per_kg:Number(form.fat_per_kg) }) });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "保存失败，请检查输入");
    }
    const goals = await response.json(); Object.assign(form, goals); void writeCache(cacheKeys.goals, goals); message.value = "目标已保存"; emit("saved", goals);
  } catch (error) {
    message.value = error.message || "保存失败，请稍后重试";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section class="card settings-view">
    <p class="section-kicker">DAILY GOALS</p><h2>每日目标设置</h2>
    <p class="settings-tip">输入当前体重即可自动计算目标，也可以调整每公斤营养系数。</p>
    <form class="settings-form" novalidate @submit.prevent="save">
      <label class="weight-field">当前体重（kg）<input v-model.number="form.weight_kg" type="number" min="1" step="1" required /></label>
      <div class="coefficient-fields">
        <label>碳水系数（g/kg）<input v-model.number="form.carbs_per_kg" type="number" min="0.1" step="1" required /></label>
        <label>蛋白质系数（g/kg）<input v-model.number="form.protein_per_kg" type="number" min="0.1" step="1" required /></label>
        <label>脂肪系数（g/kg）<input v-model.number="form.fat_per_kg" type="number" min="0.1" step="1" required /></label>
      </div>
      <div class="goal-preview">
        <article><span>卡路里目标</span><strong>{{ preview.calories }}</strong><small>kcal</small></article>
        <article><span>碳水目标</span><strong>{{ preview.carbs }}</strong><small>g</small></article>
        <article><span>蛋白质目标</span><strong>{{ preview.protein }}</strong><small>g</small></article>
        <article><span>脂肪目标</span><strong>{{ preview.fat }}</strong><small>g</small></article>
      </div>
      <button class="primary" :disabled="saving">{{ saving ? "保存中…" : "保存目标" }}</button>
    </form><p v-if="message" class="success">{{ message }}</p>
  </section>
</template>
