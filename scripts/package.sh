#!/usr/bin/env bash
# ============================================================
# QuantLoom·量梭 — Linux/macOS 打包脚本
# 生成可分发安装包: quant_loom-{version}-linux.tar.gz
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ---- 版本信息 ----
VERSION="${QUANT_LOOM_VERSION:-$(date +%Y%m%d)}"
PACKAGE_NAME="quant_loom-${VERSION}-linux"
BUILD_DIR="$PROJECT_ROOT/build/$PACKAGE_NAME"
DIST_DIR="$PROJECT_ROOT/dist"
FRONTEND_DIST="$PROJECT_ROOT/frontend/dist"

echo "============================================"
echo " QuantLoom·量梭 — Linux 打包工具"
echo " Version: $VERSION"
echo "============================================"

# ---- 1. 清理旧构建 ----
echo "[1/6] 清理旧构建..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# ---- 2. 前端构建 (如果 dist 不存在或源码更新) ----
echo "[2/6] 前端构建..."
if [ ! -d "$FRONTEND_DIST" ] || [ ! -f "$FRONTEND_DIST/index.html" ]; then
    echo "  前端 dist 不存在，正在构建..."
    if [ -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        (cd "$PROJECT_ROOT/frontend" && npm run build) || {
            echo "  ⚠️ 前端构建失败，跳过前端"
        }
    else
        echo "  ⚠️ node_modules 不存在，请先运行: cd frontend && npm install"
        echo "  跳过前端构建"
    fi
else
    echo "  前端 dist 已存在，跳过构建"
fi

# ---- 3. 复制项目文件 ----
echo "[3/6] 复制项目文件..."

# 核心 Python 包 (排除 __pycache__)
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$PROJECT_ROOT/quant_loom" "$BUILD_DIR/"
# 配置
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$PROJECT_ROOT/config" "$BUILD_DIR/"
# 脚本
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$PROJECT_ROOT/scripts" "$BUILD_DIR/"
# 测试
if [ -d "$PROJECT_ROOT/tests" ]; then
    rsync -a --exclude='__pycache__' --exclude='*.pyc' "$PROJECT_ROOT/tests" "$BUILD_DIR/"
fi

# 前端构建产物
if [ -d "$FRONTEND_DIST" ] && [ -f "$FRONTEND_DIST/index.html" ]; then
    mkdir -p "$BUILD_DIR/frontend/dist"
    cp -r "$FRONTEND_DIST"/* "$BUILD_DIR/frontend/dist/"
fi

# 根目录文件
for f in requirements.txt pyproject.toml .env.example; do
    if [ -f "$PROJECT_ROOT/$f" ]; then
        cp "$PROJECT_ROOT/$f" "$BUILD_DIR/"
    fi
done

# ---- 4. 生成平台启动脚本 ----
echo "[4/6] 生成启动器脚本..."

cat > "$BUILD_DIR/start_api.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# QuantLoom·量梭 — FastAPI 服务启动器
set -euo pipefail
cd "$(dirname "$0")"

# 默认端口
PORT="${1:-9090}"
HOST="${2:-0.0.0.0}"

echo "=== QuantLoom·量梭 API Server ==="
echo "Starting on http://${HOST}:${PORT}"
echo ""

# 激活虚拟环境 (如有)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

exec uvicorn quant_loom.api.app:app --host "$HOST" --port "$PORT"
LAUNCHER
chmod +x "$BUILD_DIR/start_api.sh"

cat > "$BUILD_DIR/start_worker.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# QuantLoom·量梭 — Celery Worker 启动器
set -euo pipefail
cd "$(dirname "$0")"

echo "=== QuantLoom·量梭 Celery Worker ==="

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

exec celery -A quant_loom.tasks.celery_app worker \
    -l info --concurrency=2 --max-tasks-per-child=50
LAUNCHER
chmod +x "$BUILD_DIR/start_worker.sh"

cat > "$BUILD_DIR/start_beat.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# QuantLoom·量梭 — Celery Beat 定时调度器
set -euo pipefail
cd "$(dirname "$0")"

echo "=== QuantLoom·量梭 Celery Beat ==="

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

exec celery -A quant_loom.tasks.celery_app beat \
    -l info --scheduler celery.beat:PersistentScheduler
LAUNCHER
chmod +x "$BUILD_DIR/start_beat.sh"

cat > "$BUILD_DIR/start_scanner.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# QuantLoom·量梭 — 单次扫描
set -euo pipefail
cd "$(dirname "$0")"

echo "=== QuantLoom·量梭 Scanner ==="

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

exec python scripts/run_scanner.py "$@"
LAUNCHER
chmod +x "$BUILD_DIR/start_scanner.sh"

# ---- 5. 生成安装脚本 ----
cat > "$BUILD_DIR/install.sh" << 'INSTALLER'
#!/usr/bin/env bash
# QuantLoom·量梭 — 一键安装
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo " QuantLoom·量梭 安装向导"
echo "============================================"
echo ""

# Python 版本检查
PYTHON=""
for py in python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" --version 2>&1 | grep -oP '\d+\.\d+')
        if [ "$(echo "$ver >= 3.11" | bc -l 2>/dev/null || echo 0)" = "1" ] || [ "${ver%%.*}" -ge 3 ] && [ "${ver##*.}" -ge 11 ] 2>/dev/null; then
            PYTHON="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 需要 Python 3.11+，未找到"
    echo "   Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    echo "   CentOS/RHEL:   sudo dnf install python3.12"
    echo "   macOS:         brew install python@3.12"
    exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# 创建虚拟环境
echo ""
echo "[1/3] 创建虚拟环境..."
$PYTHON -m venv .venv
source .venv/bin/activate

# 安装依赖
echo "[2/3] 安装 Python 依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q 2>/dev/null || true

# 初始化配置
echo "[3/3] 初始化配置..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  📝 已创建 .env，请编辑填入数据库、LLM、邮箱等配置:"
    echo "     vim .env  (或 nano .env)"
    echo ""
    echo "  必填项:"
    echo "    - MYSQL_HOST / MYSQL_PASSWORD"
    echo "    - LLM 配置 (LLAMA_BASE_URL 或 OPENAI_API_KEY)"
    echo "    - SMTP 配置 (如需邮件通知)"
else
    echo "  ✅ .env 已存在，跳过"
fi

echo ""
echo "============================================"
echo " ✅ 安装完成！"
echo "============================================"
echo ""
echo "配置数据库 (首次):"
echo "  source .venv/bin/activate"
echo "  python scripts/init_db.py"
echo ""
echo "启动服务:"
echo "  ./start_api.sh          # API 服务 (端口 9090)"
echo "  ./start_scanner.sh      # 手动扫描"
echo ""
echo "定时任务 (需要 Redis):"
echo "  ./start_worker.sh       # Celery Worker"
echo "  ./start_beat.sh         # Celery Beat"
echo ""
INSTALLER
chmod +x "$BUILD_DIR/install.sh"

# ---- 6. 打包 ----
echo "[5/6] 打包 $PACKAGE_NAME.tar.gz ..."
cd "$PROJECT_ROOT/build"
tar czf "$DIST_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"

# 计算校验和
if command -v sha256sum &>/dev/null; then
    sha256sum "$DIST_DIR/$PACKAGE_NAME.tar.gz" > "$DIST_DIR/$PACKAGE_NAME.tar.gz.sha256"
elif command -v shasum &>/dev/null; then
    shasum -a 256 "$DIST_DIR/$PACKAGE_NAME.tar.gz" > "$DIST_DIR/$PACKAGE_NAME.tar.gz.sha256"
fi

# 清理临时目录
rm -rf "$BUILD_DIR"

echo "[6/6] ✅ 打包完成!"
echo ""
echo "  📦 $DIST_DIR/$PACKAGE_NAME.tar.gz"
if [ -f "$DIST_DIR/$PACKAGE_NAME.tar.gz.sha256" ]; then
    echo "  🔐 $DIST_DIR/$PACKAGE_NAME.tar.gz.sha256"
fi

# 文件大小
SIZE=$(du -h "$DIST_DIR/$PACKAGE_NAME.tar.gz" | cut -f1)
echo "  📏 大小: $SIZE"
echo ""
