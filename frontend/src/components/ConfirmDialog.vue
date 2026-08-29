<script setup>
import { onBeforeUnmount, onMounted } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  itemName: { type: String, default: "" },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(["cancel", "confirm"]);

function cancel() {
  if (!props.loading) emit("cancel");
}

function onKeydown(event) {
  if (props.open && event.key === "Escape") cancel();
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div v-if="open" class="confirm-overlay" role="presentation" @pointerdown.self="cancel">
        <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
          <p class="section-kicker">CONFIRM DELETE</p>
          <h2 id="confirm-title">确认删除</h2>
          <p>确定要删除“<strong>{{ itemName }}</strong>”吗？</p>
          <div class="confirm-actions">
            <button type="button" class="cancel-button" :disabled="loading" @click="cancel">取消</button>
            <button type="button" class="danger-button" :disabled="loading" @click="emit('confirm')">
              {{ loading ? "删除中…" : "确认删除" }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-overlay{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:20px;background:#16251b66;backdrop-filter:blur(2px)}
.confirm-dialog{width:min(390px,100%);padding:24px;border:1px solid #dce7de;border-radius:20px;background:#fff;box-shadow:0 20px 60px #17271c33}
.confirm-dialog h2{margin:0;font-size:21px}.confirm-dialog>p:not(.section-kicker){margin:14px 0 22px;color:#667169;line-height:1.6}.confirm-dialog strong{color:#18221d}
.confirm-actions{display:flex;justify-content:flex-end;gap:10px}.confirm-actions button{height:40px;padding:0 17px;border-radius:9px;font-weight:750}.cancel-button{color:#2f855a;background:#edf7f0}.danger-button{color:#fff;background:#c23b32}.danger-button:hover{background:#a92f28}.confirm-actions button:disabled{cursor:not-allowed;opacity:.6}
.dialog-fade-enter-active,.dialog-fade-leave-active{transition:opacity .15s ease}.dialog-fade-enter-from,.dialog-fade-leave-to{opacity:0}
@media(max-width:480px){.confirm-overlay{align-items:end;padding:12px}.confirm-dialog{padding:21px;border-radius:18px}.confirm-actions{display:grid;grid-template-columns:1fr 1fr}.confirm-actions button{width:100%}}
</style>
