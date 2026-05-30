# Mini-HTTP-Server

从 Socket 开始手写一个 HTTP/1.1 服务器，不依赖任何 Web 框架。

写这个项目的初衷很简单：打 CTF 时天天用 Burp 抓包，用 Flask 写题，但对 HTTP 报文究竟怎么解析、TCP 连接怎么处理一知半解。所以决定从最底层的 `socket()` 开始，一行行把 HTTP 服务器垒出来。

## 做了什么

- **纯 socket 实现** — 不调 `http.server`，不调任何框架，自己解析 HTTP 请求行、请求头、请求体
- **多线程处理** — 每个连接开一个守护线程，不会因为一个慢客户端卡住整个服务
- **静态文件服务** — 根据扩展名自动推断 MIME 类型（HTML / CSS / 图片 / 二进制）
- **POST 表单解析** — 手动从请求体中拆出 `application/x-www-form-urlencoded` 数据

## 安全方面踩的坑

写的过程中刻意复现了几个经典 Web 漏洞，然后在代码层面堵上：

1. **目录穿越** — 最开始用字符串替换去 `../`，发现双写 `....//` 就能绕过。后来改用 `os.path.abspath` 算出真实路径再和 `www/` 做前缀比较，才算堵死
2. **暴力破解限速** — 登录接口加了 IP 级别的失败计数，错 3 次就拉黑（返回 403）。用 `attack.py` 跑字典验证过确实能拦住
3. **密码哈希** — 存的是 SHA-256 哈希而不是明文，虽然没加盐但对学习来说够用了

## 文件说明

```
├── server.py           # 主程序，约 280 行
├── attack.py           # 字典爆破脚本（用来测试限速机制）
├── test_colors.py      # 集成测试，彩色日志输出
├── www/
│   ├── index.html      # 带登录表单的首页
│   └── school.jpg      # 测试用静态资源
└── explaination/       # 源码逐行解析笔记
```

## 运行

需要 Python 3，不用装任何第三方库：

```bash
python server.py
# 浏览器打开 http://127.0.0.1:8081
# 登录: admin / 123456
```

测试限速机制：

```bash
python test_colors.py   # 自动测 8 种请求场景
python attack.py         # 跑字典看多久被 ban
```

## 学了什么

- TCP 连接的生命周期：`socket → bind → listen → accept → recv → send → close`
- HTTP 报文结构：`\r\n\r\n` 分隔头与体，`Content-Length` 决定读多少字节
- 多线程并发模型：daemon 线程 + `with` 语句自动关闭 socket
- 安全编码意识：永远不信任用户输入路径、永远不存明文密码

## 待完善

- [ ] 用线程池替代无限创建线程
- [ ] 失败计数加过期时间（目前重启才清空）
- [ ] 登录成功重置失败计数
- [ ] 支持更多 HTTP 方法（目前只做了 GET/POST）
