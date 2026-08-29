<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({ open: Boolean, loading: Boolean, error: { type: String, default: "" } });
const emit = defineEmits(["cancel", "unlock"]);
const password = ref("");
const passwordInput = ref(null);

watch(() => props.open, async open => {
  if (!open) { password.value = ""; return; }
  await nextTick(); passwordInput.value?.focus();
});

function cancel() { if (!props.loading) emit("cancel"); }
function keydown(event) { if (event.key === "Escape") cancel(); }
function submit() { if (password.value && !props.loading) emit("unlock", password.value); }
</script>

<template>
  <Teleport to="body">
    <Transition name="unlock-fade">
      <div v-if="open" class="unlock-overlay" @pointerdown.self="cancel" @keydown="keydown">
        <section class="unlock-dialog" role="dialog" aria-modal="true" aria-labelledby="unlock-title">
          <p class="section-kicker">EDIT ACCESS</p><h2 id="unlock-title">解锁编辑</h2>
          <p>查看无需密码。新增、修改、删除和 AI 解析需要先解锁。</p>
          <form @submit.prevent="submit">
            <label>编辑密码<input ref="passwordInput" v-model="password" type="password" autocomplete="current-password" required /></label>
            <p v-if="error" class="unlock-error">{{ error }}</p>
            <div class="unlock-actions"><button type="button" class="cancel-button" :disabled="loading" @click="cancel">取消</button><button class="unlock-button" :disabled="loading||!password">{{loading?'验证中…':'解锁'}}</button></div>
          </form>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.unlock-overlay{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:20px;background:#16251b66;backdrop-filter:blur(2px)}.unlock-dialog{width:min(390px,100%);padding:24px;border:1px solid #dce7de;border-radius:20px;background:#fff;box-shadow:0 20px 60px #17271c33}.unlock-dialog h2{margin:0;font-size:21px}.unlock-dialog>p:not(.section-kicker){margin:12px 0 20px;color:#667169;line-height:1.6}.unlock-error{margin:9px 0 0;color:#b42318;font-size:12px}.unlock-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}.unlock-actions button{height:40px;padding:0 18px;border-radius:9px;font-weight:750}.cancel-button{color:#2f855a;background:#edf7f0}.unlock-button{color:#fff;background:#2f855a}.unlock-actions button:disabled{cursor:not-allowed;opacity:.6}.unlock-fade-enter-active,.unlock-fade-leave-active{transition:opacity .15s ease}.unlock-fade-enter-from,.unlock-fade-leave-to{opacity:0}@media(max-width:480px){.unlock-overlay{align-items:end;padding:12px}.unlock-dialog{padding:21px;border-radius:18px}.unlock-actions{display:grid;grid-template-columns:1fr 1fr}.unlock-actions button{width:100%}}
</style>
