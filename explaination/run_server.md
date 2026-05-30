# run_server 函数详解

> 所在文件：[server.py:221-265](server.py#L221-L265)

## 作用

启动 HTTP 服务器的**入口函数**。创建 socket → 绑定端口 → 死循环等待连接 → 每来一个连接就开新线程处理。

## 函数签名

```python
def run_server():
```

无参数，所有配置写死在函数里。

---

## 第 1 步：创建 Socket（第 223 行）

```python
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

| 参数 | 含义 |
|---|---|
| `socket.AF_INET` | 使用 **IPv4** 地址族 |
| `socket.SOCK_STREAM` | 使用 **TCP** 协议（`STREAM` = 流式传输，可靠有序） |

> `AF_INET` + `SOCK_STREAM` = 标准的 TCP/IP 通信方式。

---

## 第 2 步：端口复用（第 226 行）

```python
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```

| 语法 | 含义 |
|---|---|
| `setsockopt(层级, 选项, 值)` | 设置 socket 选项 |
| `SO_REUSEADDR` | 允许重用 `TIME_WAIT` 状态的端口 |

**为什么要加**：关闭脚本后立即重启，如果不设这个选项，系统会报 `Address already in use`，因为操作系统默认要把端口标记为"冷却中"几分钟才释放。`SO_REUSEADDR` 跳过这个等待。

---

## 第 3 步：绑定 + 监听（第 229-234 行）

```python
HOST = "127.0.0.1"   # 只允许本机访问
PORT = 8081
server_socket.bind((HOST, PORT))
server_socket.listen(5)
```

| 语法 | 含义 |
|---|---|
| `.bind((host, port))` | 把 socket 绑定到指定 IP + 端口。注意传的是**元组**（双层括号） |
| `"127.0.0.1"` | **本地回环地址**，只能本机访问，外部网络无法连接（安全） |
| `.listen(n)` | 开始监听。`n` = 操作系统允许的**等待队列最大长度**（排队的连接） |

---

## 第 4 步：死循环接收连接（第 239-259 行）

```python
while True:
    client_socket, client_address = server_socket.accept()
    print(f"收到来自{client_address}的连接")

    client_thread = threading.Thread(
        target=handle_client,
        args=(client_socket, client_address)
    )
    client_thread.daemon = True
    client_thread.start()
```

### 4.1 accept() — 阻塞等待

```python
client_socket, client_address = server_socket.accept()
```

| 语法 | 含义 |
|---|---|
| `.accept()` | **阻塞**函数。没有客户端连接时，程序**卡在这里不动**，直到有连接进来 |
| 返回值 | 一个元组 `(新socket, 客户端地址)` |

**关键概念**：`server_socket` 只负责"接电话"，`.accept()` 返回的 `client_socket` 是每通电话的"专线"。

### 4.2 创建子线程

```python
client_thread = threading.Thread(
    target=handle_client,
    args=(client_socket, client_address)
)
```

| 参数 | 含义 |
|---|---|
| `target=函数名` | 线程要执行的函数，**不加括号**（传函数本身，不调用它） |
| `args=(参数1, 参数2)` | 传给 target 函数的参数，以**元组**形式 |

如果不加括号还有疑问——`target=handle_client` 相当于"这个线程启动时去调用 `handle_client`"，而不是"立刻调用它"。

### 4.3 守护线程 + 启动

```python
client_thread.daemon = True
client_thread.start()
```

| 语法 | 含义 |
|---|---|
| `.daemon = True` | 设为**守护线程**。主线程退出时，守护线程自动销毁（不等它干完活） |
| `.start()` | 启动线程。内部自动调用 `handle_client(client_socket, client_address)` |

**主线程不等待**：`.start()` 一调用立刻返回，主线程直接回到 `while True` 顶部，继续 `accept()` 等下一个连接。这才是**并发**的关键——不用等当前请求处理完就能接下一个。

---

## 第 5 步：优雅退出（第 261-265 行）

```python
except KeyboardInterrupt:
    print("\n 正在关闭服务器...")
finally:
    server_socket.close()
```

| 语法 | 含义 |
|---|---|
| `KeyboardInterrupt` | 用户按 `Ctrl+C` 时抛出的异常。捕获它来优雅退出而不是打印大段报错 |
| `finally:` | 无论正常退出还是按 Ctrl+C，都要关闭 socket |

---

## 入口判断（第 267-268 行）

```python
if __name__ == "__main__":
    run_server()
```

| 语法 | 含义 |
|---|---|
| `__name__` | Python 的内置变量。直接运行这个文件时它的值是 `"__main__"` |
| `== "__main__"` | 判断"我是不是被直接运行的" |

**为什么这样写**：如果这个文件被别人 `import` 导入，`__name__` 不会等于 `"__main__"`，`run_server()` 就不会执行。这样同一个文件既可以当模块用，也可以直接运行。

---

## 完整的启动流程

```
run_server()
    │
    ▼
socket() → setsockopt() → bind() → listen()
    │
    ▼
while True:  ← 死循环
    │
    ▼
  accept()   ← 阻塞等待（这里会卡住）
    │
    │ 有客户端连接
    ▼
  创建 Thread(target=handle_client)
    │
    ▼
  .start()   ← 立刻返回，不等
    │
    └──→ handle_client 在子线程并行执行
    │
    ▼
  回到循环顶部，继续 accept()
```

**一句话总结**：主线程负责"接客"，每接一个就丢给新线程去服务，自己立刻回去接着等。所有客户端**同时被服务**，互不阻塞。

---

## 三个函数的关系

```
run_server()            ← 入口，接客 + 分配线程
    │
    └──→ handle_client()   ← 每个客户端一个线程
              │
              └──→ recv_http_request()   ← 收完整 HTTP 请求
```
