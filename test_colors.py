"""测试脚本：在同一个进程里启动服务器并向它发请求，展示彩色日志效果"""
import threading
import time
import urllib.request
import urllib.parse
import sys

# 先导入 server 模块（run_server 会阻塞，我们在子线程跑）
import server

def make_requests():
    """等服务器就绪后，发送一系列测试请求"""
    time.sleep(1)  # 等服务器启动

    base = "http://127.0.0.1:8081"

    tests = [
        ("GET", "/", None, "正常访问首页"),
        ("GET", "/nope.html", None, "不存在的文件 → 404"),
        ("POST", "/login", "username=admin&password=123456", "登录成功 → 200"),
        ("POST", "/login", "username=admin&password=wrong1", "登录失败 → 200"),
        ("POST", "/login", "username=admin&password=wrong2", "登录失败 → 200"),
        ("POST", "/login", "username=admin&password=wrong3", "登录失败 → 200"),
        ("POST", "/login", "username=admin&password=wrong4", "封禁触发 → 403"),
        ("GET", "/../../../etc/passwd", None, "目录穿越攻击"),
    ]

    print("\n" + "=" * 60)
    print("  开始发送测试请求...")
    print("=" * 60 + "\n")

    for method, path, body, desc in tests:
        url = base + path
        data = body.encode("utf-8") if body else None
        try:
            req = urllib.request.Request(url, data=data, method=method)
            with urllib.request.urlopen(req, timeout=3) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            status = str(e)

        print(f"  [{method:4s}] {desc:30s} → HTTP {status}")
        time.sleep(0.3)  # 间隔一下，让日志清晰可读

    print("\n" + "=" * 60)
    print("  测试完成！请向上滚动查看上方的彩色日志 ↑")
    print("=" * 60)

    # 给日志一点时间刷出来
    time.sleep(0.5)
    # 退出整个程序
    import os
    os._exit(0)


if __name__ == "__main__":
    print("\n\033[1m\033[37m  Mini HTTP Server - 彩色日志测试\033[0m\n")

    # 在子线程启动服务器
    server_thread = threading.Thread(target=server.run_server, daemon=True)
    server_thread.start()

    # 主线程发请求
    make_requests()
