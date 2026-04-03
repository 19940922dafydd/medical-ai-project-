#!/bin/bash

echo "🚀 启动医疗问答系统管理后台..."
echo "========================================"

# 检查后端是否在运行
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "❌ 后端服务未运行在端口8000"
    echo "请先启动后端服务："
    echo "  cd /Users/dafydd/Documents/medical/medical_agent"
    echo "  python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

echo "✅ 后端服务已运行 (端口 8000)"

# 查找可用的端口
for port in {8503..8510}; do
    if ! lsof -ti:$port > /dev/null 2>&1; then
        AVAILABLE_PORT=$port
        break
    fi
done

if [ -z "$AVAILABLE_PORT" ]; then
    echo "❌ 未找到可用端口 (8503-8510)"
    exit 1
fi

echo "📊 在端口 $AVAILABLE_PORT 启动管理后台..."

# 启动Streamlit管理界面
streamlit run frontend/admin_app.py --server.port $AVAILABLE_PORT --server.headless true

echo "========================================"
echo "管理后台已启动："
echo "  http://localhost:$AVAILABLE_PORT"
echo ""
echo "💡 测试分级知识库功能："
echo "  1. 点击左侧菜单中的【分级知识库管理】"
echo "  2. 在【目录树管理】中创建三级结构"
echo "  3. 在【分级文档灌注】中上传文档"
echo "  4. 在【分层切片浏览】中查看结果"
echo ""
echo "按 Ctrl+C 停止服务"