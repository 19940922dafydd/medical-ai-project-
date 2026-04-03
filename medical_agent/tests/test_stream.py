import requests
import json
import time
import sys

def test_streaming():
    url = "http://localhost:8000/stream"
    payload = {
        "query": "孕晚期肚子发紧是怎么回事？",
        "history": [
            {"role": "user", "content": "医生你好，我最近有点不舒服"},
            {"role": "assistant", "content": "你好，请问有什么可以帮助您的？"}
        ],
        "session_id": "test_session_123"
    }
    
    print("🚀 开始向 Medical Agent API 请求流式对话...")
    print("--------------------------------------------------")
    
    try:
        # 发送带 stream=True 的请求
        with requests.post(url, json=payload, stream=True) as r:
            r.raise_for_status()
            
            # 使用 iter_lines 获取 SSE 的每个 event
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data_content = decoded_line[6:] # 去掉 'data: ' 前缀
                        if data_content == "[DONE]":
                            print("\n\n✅ 流式请求结束 [DONE]")
                            break
                            
                        # 解析收到的 JSON
                        try:
                            event_data = json.loads(data_content)
                            node = event_data.get("node")
                            msg = event_data.get("message")
                            
                            # 模拟流式打字机效果输出
                            print(f"\n[{node.upper()} 节点更新] : ", end="")
                            for char in msg:
                                sys.stdout.write(char)
                                sys.stdout.flush()
                                time.sleep(0.01) # 稍微延迟一下更像打字机
                        except json.JSONDecodeError:
                            print(f"\n收到非 JSON 数据: {data_content}")
                            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保 uvicorn 正在运行：`PYTHONPATH=. uvicorn backend.main:app`")

if __name__ == "__main__":
    test_streaming()
