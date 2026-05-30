# recv_http_request 函数详解

> 所在文件：[server.py:9-41](server.py#L9-L41)

## 作用

从客户端 socket 中**完整接收一个 HTTP 请求**，返回 `(头部字符串, body字符串)`。

## 函数签名

```python
def recv_http_request(client_socket):
```

- `def` — Python 定义函数的关键字
- `client_socket` — 参数：一个 **socket 对象**，代表与某客户端的 TCP 连接

---

## 第 1 步：循环读取 HTTP 头部（第 11-16 行）

```python
data = b""
while b"\r\n\r\n" not in data:
    chunk = client_socket.recv(1024)
    if not chunk:
        break
    data += chunk
```

**逻辑**：HTTP 协议中，**头部和 body 之间用空行分隔**（即 `\r\n\r\n`）。只要还没读到，说明头没收完，继续读。

| 语法 | 含义 |
|---|---|
| `b""` | 空**字节串（bytes）**。`b` 前缀表示字节。网络传输全是字节流 |
| `b"\r\n\r\n"` | `\r\n` = CRLF = HTTP 行分隔符，两个连续 = 空行 |
| `client_socket.recv(1024)` | 从 TCP 缓冲区读最多 1024 字节。读到的长度不固定（网络状况决定） |
| `if not chunk: break` | 空字节 = 客户端断开，退出防死循环 |
| `data += chunk` | `+=` 拼接字节串 |

---

## 第 2 步：分离头部和已收到的 body（第 22-24 行）

```python
headers_raw, _, body_so_far = data.partition(b"\r\n\r\n")
headers_str = headers_raw.decode("utf-8", errors="replace")
body_bytes = body_so_far
```

**逻辑**：此时 `data` 的内容是 `头部\r\n\r\n可能部分body`，一刀切开。

| 语法 | 含义 |
|---|---|
| `.partition(sep)` | 按分隔符切成**三元组**：`(之前, 分隔符, 之后)` |
| `_` | Python 约定：下划线表示"我不关心这个值"（接收分隔符本身） |
| `.decode("utf-8", errors="replace")` | bytes → 字符串。`errors="replace"` 遇到非法字节用 `�` 替代 |

---

## 第 3 步：解析 Content-Length（第 27-31 行）

```python
content_length = 0
for line in headers_str.splitlines():
    if line.lower().startswith("content-length:"):
        content_length = int(line.split(":", 1)[1].strip())
        break
```

**逻辑**：从请求头中找到 `Content-Length: 数字`，提取 body 的字节长度。

| 语法 | 含义 |
|---|---|
| `.splitlines()` | 按换行符切成**列表**（list，即数组） |
| `for line in ...:` | foreach 遍历 |
| `.lower()` | 转小写，大小写不敏感匹配 |
| `.startswith(s)` | 检查是否以 `s` 开头，返回 `True/False` |
| `.split(":", 1)` | 用冒号分割，`1` = 最多切一刀（防止 value 含冒号被误切） |
| `[1]` | 取列表第二个元素，即冒号后面的值 |
| `.strip()` | 去掉首尾空白 |
| `int(...)` | 字符串转整数 |

---

## 第 4 步：补读剩余 body（第 33-39 行）

```python
remaining = content_length - len(body_bytes)
while remaining > 0:
    chunk = client_socket.recv(min(1024, remaining))
    if not chunk:
        break
    body_bytes += chunk
    remaining -= len(chunk)
```

**逻辑**：第一次读数据时 body 可能没收全（TCP 不保证一次收完），这里补读。

| 语法 | 含义 |
|---|---|
| `len(body_bytes)` | 返回字节串长度 |
| `remaining` | 还差多少字节 |
| `min(1024, remaining)` | 取较小值：每次最多 1024，但不超过剩余量（防止多读吞掉下一个请求） |
| `remaining -= len(chunk)` | `-=` 等价于 `remaining = remaining - len(chunk)` |

---

## 第 5 步：返回（第 41 行）

```python
return headers_str, body_bytes.decode("utf-8", errors="replace")
```

返回一个**元组（tuple）**，调用方用**解包**接收：

```python
headers_part, body_part = recv_http_request(client_socket)
```

---

## 整体流程

```
客户端发送 HTTP 请求
        │
        ▼
┌─ 循环读字节 ──────┐
│ 读到 \r\n\r\n 了吗? │─ 否 ─→ recv(1024)，拼接
└───────────────────┘
        │ 是
        ▼
 用 \r\n\r\n 切开 data
        │
   ┌────┴────┐
   ▼         ▼
 头部     body片段（可能不全）
   │         │
   ▼         ▼
找 Content-Length   算还需要多少字节
                    └─ 不够就继续 recv ─→ 补齐
        │
        ▼
  return (头部字符串, body字符串)
```
