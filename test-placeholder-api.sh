#!/bin/bash

# 验证占位视频 API 配置脚本

echo "🔍 验证 API Key 配置..."
echo ""

# 加载 .env 文件
source .env

# 验证 Pixabay API
echo "📺 测试 Pixabay API..."
if [ -n "$PIXABAY_API_KEY" ] && [ "$PIXABAY_API_KEY" != "请替换为你的 Pixabay API Key" ]; then
    RESPONSE=$(curl -s "https://pixabay.com/api/?key=${PIXABAY_API_KEY}&q=nature&per_page=1")
    if echo "$RESPONSE" | grep -q '"total"'; then
        echo "✅ Pixabay API 正常！"
        echo "   返回结果：$(echo "$RESPONSE" | grep -o '"total":[0-9]*')"
    else
        echo "❌ Pixabay API 失败，请检查 API Key"
        echo "   响应：$RESPONSE"
    fi
else
    echo "⚠️  Pixabay API Key 未配置"
fi
echo ""

# 验证 Pexels API
echo "📺 测试 Pexels API..."
if [ -n "$PEXELS_API_KEY" ] && [ "$PEXELS_API_KEY" != "请替换为你的 Pexels API Key" ]; then
    RESPONSE=$(curl -s -X GET "https://api.pexels.com/videos/v1/search?query=nature&per_page=1" \
        -H "Authorization: ${PEXELS_API_KEY}")
    if echo "$RESPONSE" | grep -q '"total"'; then
        echo "✅ Pexels API 正常！"
        echo "   返回结果：$(echo "$RESPONSE" | grep -o '"total":[0-9]*')"
    else
        echo "❌ Pexels API 失败，请检查 API Key"
        echo "   响应：$RESPONSE"
    fi
else
    echo "⚠️  Pexels API Key 未配置"
fi
echo ""

echo "📋 当前配置："
echo "   VIDEO_BG_MODE=$VIDEO_BG_MODE"
echo "   PLACEHOLDER_PROVIDER=$PLACEHOLDER_PROVIDER"
echo "   PLACEHOLDER_MIN_WIDTH=$PLACEHOLDER_MIN_WIDTH"
echo "   PLACEHOLDER_MIN_HEIGHT=$PLACEHOLDER_MIN_HEIGHT"
echo "   PLACEHOLDER_CACHE_MAX_MB=$PLACEHOLDER_CACHE_MAX_MB"
echo ""
