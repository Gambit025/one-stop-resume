#!/usr/bin/env python3
"""测试 Anthropic API 是否有效"""
import os
import anthropic

ANTHROPIC_API_KEY = os.environ.get("API") or os.environ.get("ANTHROPIC_API_KEY") or None
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL") or "https://apicn.unifyllm.top"

print(f"API Key 前缀: {ANTHROPIC_API_KEY[:20] if ANTHROPIC_API_KEY else 'None'}...")
print(f"API Key 长度: {len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0}")
print(f"Base URL: {ANTHROPIC_BASE_URL}")

if not ANTHROPIC_API_KEY:
    print("\n❌ 错误: 未找到 API Key!")
    print("请设置环境变量: export ANTHROPIC_API_KEY='your-key'")
    exit(1)

try:
    print("\n正在测试 API 连接...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": "回复'API 测试成功'"}]
    )

    print(f"\n✅ API 测试成功!")
    print(f"模型响应: {message.content[0].text}")

except anthropic.AuthenticationError as e:
    print(f"\n❌ 认证失败: API Key 无效")
    print(f"错误详情: {e}")

except anthropic.RateLimitError as e:
    print(f"\n❌ 速率限制: 请求过多或额度不足")
    print(f"错误详情: {e}")

except Exception as e:
    print(f"\n❌ 其他错误: {type(e).__name__}")
    print(f"错误详情: {e}")
