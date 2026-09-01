const DB_NAME = "calorie-tracker-cache";
const DB_VERSION = 1;
const STORE_NAME = "responses";

let databasePromise;

function openDatabase() {
  if (!globalThis.indexedDB) return Promise.reject(new Error("IndexedDB unavailable"));
  if (databasePromise) return databasePromise;
  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) database.createObjectStore(STORE_NAME, { keyPath: "key" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
    request.onblocked = () => reject(new Error("IndexedDB open blocked"));
  }).catch(error => {
    databasePromise = null;
    throw error;
  });
  return databasePromise;
}

function runTransaction(mode, action) {
  return openDatabase().then(database => new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode);
    const store = transaction.objectStore(STORE_NAME);
    let result;
    try { result = action(store); } catch (error) { reject(error); return; }
    transaction.oncomplete = () => resolve(result?.result);
    transaction.onerror = () => reject(transaction.error || result?.error || new Error("IndexedDB transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("IndexedDB transaction aborted"));
  }));
}

export async function readCache(key) {
  try {
    const entry = await runTransaction("readonly", store => store.get(key));
    return entry?.value ?? null;
  } catch { return null; }
}

export async function writeCache(key, value) {
  try {
    await runTransaction("readwrite", store => store.put({ key, value, updatedAt: Date.now() }));
  } catch { /* Cache failures must never block normal page behavior. */ }
}

export async function deleteCachePrefix(prefix) {
  try {
    await runTransaction("readwrite", store => {
      const request = store.openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (!cursor) return;
        if (String(cursor.key).startsWith(prefix)) cursor.delete();
        cursor.continue();
      };
      return request;
    });
  } catch { /* Invalidation failures must not block server-backed writes. */ }
}

function normalizedParams(params) {
  return [...new URLSearchParams(params).entries()]
    .sort(([leftKey, leftValue], [rightKey, rightValue]) => leftKey.localeCompare(rightKey) || leftValue.localeCompare(rightValue))
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
}

export const cacheKeys = {
  goals: "goals",
  records: date => `records:${date}`,
  stats: date => `stats:${date}`,
  trend: (endDate, days) => `trend:${endDate}:${days}`,
  foods: params => `foods:${normalizedParams(params)}`,
};
