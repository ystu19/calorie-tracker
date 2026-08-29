# calorie-tracker

卡路里记录系统（Vue 3 + Vite + FastAPI + SQLite）。

## 目录

- `frontend/` — Vue 3 + Vite
- `backend/` — FastAPI + SQLite

## 环境要求

- Python 3.11+（本机已用 3.14 验证）
- Node.js 20+（用于前端 `npm`）
- Git（可选，用于版本管理）

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API 文档：http://127.0.0.1:8000/docs

## 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端开发服务器：http://127.0.0.1:5173  
开发环境下 `/api` 会代理到后端 `8000` 端口。
