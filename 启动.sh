#!/usr/bin/env bash
# 农作物病虫害叶片识别系统 - macOS / Linux 一键启动
# 用法：bash 启动.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8001
FRONTEND_PORT=5176

echo "=============================================="
echo " 农作物病虫害叶片识别系统"
echo "=============================================="

# ---------- 1. 检查环境 ----------
command -v python3 >/dev/null 2>&1 || { echo "❌ 没找到 python3，请先安装 Python 3.10+"; exit 1; }
command -v npm    >/dev/null 2>&1 || { echo "❌ 没找到 npm，请先安装 Node.js 18+"; exit 1; }

# ---------- 2. 检查 .env ----------
if [ ! -f "$ROOT/server/.env" ]; then
  echo "⚠️  没找到 server/.env，从模板复制一份"
  cp "$ROOT/server/.env.example" "$ROOT/server/.env"
  echo "   请先编辑 server/.env 填数据库密码，然后重新运行本脚本"
  exit 1
fi

# ---------- 3. 后端依赖 ----------
cd "$ROOT/server"
if [ ! -d ".venv" ]; then
  echo "📦 创建 Python 虚拟环境…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if ! python -c "import fastapi" >/dev/null 2>&1; then
  echo "📦 安装后端依赖…"
  pip install -q -r requirements.txt
fi

# ---------- 4. 前端依赖 ----------
cd "$ROOT/web-v4"
if [ ! -d "node_modules" ]; then
  echo "📦 安装前端依赖…"
  npm install
fi

# ---------- 5. 启动 ----------
echo "🚀 启动后端 http://127.0.0.1:$BACKEND_PORT"
cd "$ROOT/server"
python -m uvicorn main:app --host 127.0.0.1 --port $BACKEND_PORT &
BACK_PID=$!

sleep 4
echo "🚀 启动前端 http://127.0.0.1:$FRONTEND_PORT"
cd "$ROOT/web-v4"
npm run dev -- --port $FRONTEND_PORT &
FRONT_PID=$!

echo ""
echo "=============================================="
echo " 前端：http://127.0.0.1:$FRONTEND_PORT"
echo " 接口：http://127.0.0.1:$BACKEND_PORT/docs"
echo " 按 Ctrl+C 停止全部服务"
echo "=============================================="

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null' INT TERM
wait
