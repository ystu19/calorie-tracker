let unlockHandler = null;
let pendingUnlock = null;

export function setUnlockHandler(handler) {
  unlockHandler = handler;
}

export async function ensureUnlocked() {
  const status = await fetch("/api/auth/status");
  if (status.ok && (await status.json()).unlocked) return;
  if (!unlockHandler) throw new Error("需要先解锁编辑");
  pendingUnlock ||= Promise.resolve().then(() => unlockHandler()).finally(() => { pendingUnlock = null; });
  await pendingUnlock;
}

export async function authFetch(input, init) {
  let response = await fetch(input, init);
  if (response.status !== 401 || String(input).includes("/api/auth/")) return response;
  await ensureUnlocked();
  response = await fetch(input, init);
  return response;
}
