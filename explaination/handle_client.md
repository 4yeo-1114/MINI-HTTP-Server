# handle_client 函数详解

> 所在文件：[server.py:43-217](server.py#L43-L217)

## 作用

每个客户端连接进来后，由**一个独立线程**运行这个函数。接收请求 → 判断路由 → 返回响应。

## 函数签名

```python
def handle_client(client_socket, client_address):
```

| 参数 | 含义 |
|---|---|
| `client_socket` | 该客户端专属的 socket，用来收发数据 |
| `client_address` | 元组 `(IP地址, 端口号)`，如 `("127.0.0.1", 54321)` |

---

## 整体结构（5 大块）

```
handle_client
├── 1. 接收请求
├── 2. 解析请求行
├── 3. POST /login → 登录逻辑
├── 4. 其他路径 → 返回本地文件
└── 5. 异常处理 + 最终收尾
```

---

## 第 1 块：接收请求（第 47-49 行）

```python
headers_part, body_part = recv_http_request(client_socket)
if not headers_part:
    return
```

调用前面写的 `recv_http_request`，用**元组解包**拿到头部字符串和 body 字符串。如果头部为空（客户端断开），直接 `return` 结束这个线程。

---

## 第 2 块：解析请求行（第 51-56 行）

```python
request_lines = headers_part.splitlines()
request_line = request_lines[0]
print(f"\n收到请求行:{request_line}")

method, path, version = request_line.split(" ")
```

**逻辑**：HTTP 请求的第一行长这样：

```
GET /index.html HTTP/1.1
```

按空格切开，三个变量分别拿到：

| 变量 | 值 |
|---|---|
| `method` | `GET`、`POST` 等 |
| `path` | `/index.html`、`/login` 等 |
| `version` | `HTTP/1.1` |

> `print(f"...")` 中的 `f` 前缀是 **f-string**：花括号里的变量自动替换为实际值。

---

## 第 3 块：POST /login — 登录处理（第 59-138 行）

### 3.1 前端防爆破（第 63-76 行）

```python
client_ip = client_address[0]

if FAILED_ATTEMPTS.get(client_ip, 0) >= 3:
    # 返回 403 Forbidden
    return
```

| 语法 | 含义 |
|---|---|
| `client_address[0]` | 元组第一个元素就是 IP 地址 |
| `FAILED_ATTEMPTS` | 全局字典（第 7 行），记录各 IP 的失败次数 |
| `.get(key, 默认值)` | 字典取值的**安全方法**。键不存在时返回默认值而不报错（`[key]` 取不存在的键会 `KeyError` 崩溃）|

如果某 IP 连续失败 ≥ 3 次，直接返回 403 并**结束函数**，后续逻辑不再执行。

### 3.2 解析 POST body（第 80-93 行）

POST 的 body 长这样：`username=admin&password=123456`

```python
params = {}
for pair in body_part.split("&"):
    if "=" in pair:
        k, v = pair.split("=")
        params[k] = v
```

| 语法 | 含义 |
|---|---|
| `body_part.split("&")` | 按 `&` 切开，得到 `["username=admin", "password=123456"]` |
| `k, v = pair.split("=")` | 解包：把列表两个元素分别赋给 k 和 v |
| `params[k] = v` | 往字典里存键值对 |

循环结束：`params = {"username": "admin", "password": "123456"}`

### 3.3 密码验证（第 99-122 行）

```python
pwd_hash = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
admin_real_hash = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"

if user == "admin" and pwd_hash == admin_real_hash:
    result_html = f"<h1 style='color:green;'>登录成功！ 欢迎回来 {user}</h1>"
else:
    FAILED_ATTEMPTS[client_ip] = FAILED_ATTEMPTS.get(client_ip, 0) + 1
    attempts_left = 3 - FAILED_ATTEMPTS[client_ip]
    result_html = f"<h1 style='color:red;'>登录失败 账号或密码错误 你还有{attempts_left}次机会</h1>"
```

**核心思路**：不存储明文密码，只存 SHA-256 哈希值。

| 语法 | 含义 |
|---|---|
| `"字符串".encode("utf-8")` | 字符串 → 字节串，哈希函数只接受字节 |
| `hashlib.sha256(...)` | 创建 SHA-256 哈希对象 |
| `.hexdigest()` | 输出 64 位十六进制字符串（如 `"8d969eef..."`） |
| `==` | 比较哈希值是否相同 |

**哈希特点**：单向不可逆。知道 `"8d969eef..."` 也无法反推出原密码是 `"123456"`。

失败时 `FAILED_ATTEMPTS[client_ip]` 会 +1。连续 3 次失败触发 3.1 的封禁。

### 3.4 构造并发送 HTTP 响应（第 123-137 行）

```python
body_bytes = result_html.encode("utf-8")
http_response = (
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: text/html; charset=utf-8\r\n"
    f"Content-Length: {len(body_bytes)}\r\n"
    "Connection: close\r\n"
    "\r\n"
).encode("utf-8") + body_bytes

client_socket.sendall(http_response)
```

**逻辑**：HTTP 响应 = **头部** + **空行（`\r\n\r\n`）** + **body**。

| 语法 | 含义 |
|---|---|
| `(...)` 跨行 | Python 中括号内的字符串可跨行，自动拼接 |
| `.encode("utf-8")` | 头部字符串 → 字节 |
| `+ body_bytes` | 头部字节 + body 字节拼在一起 |
| `sendall()` | 把整个响应的字节全部发出，保证发完才返回 |

---

## 第 4 块：返回本地文件（第 142-210 行）

代码走到这里，说明不是 POST /login，进入文件服务逻辑。

### 4.1 默认首页（第 144-145 行）

```python
if path == "/":
    path = "/index.html"
```

### 4.2 防目录穿越攻击（第 149-158 行）

```python
base_dir = os.path.abspath(os.path.join(os.getcwd(), "www"))
request_path = os.path.abspath(os.path.join(base_dir, path.lstrip("/")))
```

| 语法 | 含义 |
|---|---|
| `os.getcwd()` | 获取当前工作目录（脚本运行的文件夹） |
| `os.path.join(a, b)` | 拼接路径，自动处理 `/` 和 `\` |
| `os.path.abspath(...)` | 把相对路径转成**绝对路径** |
| `path.lstrip("/")` | 去掉路径最左边的 `/`，如 `"/../etc/passwd"` → `"../etc/passwd"` |

**为什么这样做**：防止攻击者用 `GET /../../../etc/passwd` 跳出 `www/` 目录偷看系统文件。

两次 `abspath` 之后，攻击者的 `../..` 全部被展开为实际路径，然后：

```python
if not request_path.startswith(base_dir):
    # 检测到攻击 → 拒绝访问
```

### 4.3 MIME 类型判断（第 171-182 行）

根据文件后缀设置 `Content-Type`，告诉浏览器这是什么类型的文件：

| 后缀 | Content-Type | 效果 |
|---|---|---|
| `.html` | `text/html` | 渲染为网页 |
| `.jpg` / `.jpeg` | `image/jpeg` | 显示图片 |
| `.png` | `image/png` | 显示图片 |
| `.css` | `text/css` | 样式表 |
| 其他 | `application/octet-stream` | 浏览器下载 |

### 4.4 读取文件并发送（第 184-210 行）

```python
with open(file_path, "rb") as f:
    file_content = f.read()
```

| 语法 | 含义 |
|---|---|
| `open(path, "rb")` | `r`=读，`b`=二进制模式。**不用文本模式**，因为图片、CSS 等都不是纯文本 |
| `with ... as f:` | **上下文管理器**：代码块结束自动 `close` 文件，即使中途出错也不漏关 |
| `f.read()` | 一次性读完整个文件 |

`try ... except FileNotFoundError`：文件不存在时返回 404 页面。

---

## 第 5 块：异常处理（第 212-217 行）

```python
except Exception as e:
    print(f"处理{client_address}时发生错误:{e}")
finally:
    client_socket.close()
    print(f"与{client_address}的连接已断开,释放线程")
```

| 语法 | 含义 |
|---|---|
| `try:` | 包裹可能出错的代码 |
| `except Exception as e:` | 捕获任何异常，`e` 是异常对象 |
| `finally:` | **不管是否出错都执行**。用来关闭 socket 这种必须执行的收尾工作 |
| `.close()` | 关闭 TCP 连接，释放系统资源 |

**为什么需要 `finally`**：就算前面代码报错了，也必须关 socket，否则连接泄漏。

---

## 整体路由流程

```
请求到达
    │
    ▼
recv_http_request() 接收完整请求
    │
    ▼
解析请求行 → method, path, version
    │
    ├── POST /login? ─────────┐
    │                         ▼
    │                    IP 被封禁? ──是──→ 403
    │                         │否
    │                         ▼
    │                    解析 body 表单
    │                         │
    │                         ▼
    │                    验证密码哈希
    │                    ┌───┴───┐
    │                  成功      失败
    │                    │        │
    │                    ▼        ▼
    │                  200     200(记录失败+1)
    │
    └── 其他路径 ────────────┐
                             ▼
                        /  → /index.html
                             │
                             ▼
                        防目录穿越检查
                        ┌────┴────┐
                      安全       危险
                        │        │
                        ▼        ▼
                    读文件    拒绝访问
                   ┌──┴──┐
                 存在   不存在
                  │      │
                  ▼      ▼
                200    404
```
