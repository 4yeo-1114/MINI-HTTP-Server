import socket
import os  # os 模块：提供操作系统相关的功能，这里主要用 os.path 来处理文件路径（拼接、转绝对路径等）
import threading  # 内置多线程模块：让服务器能同时处理多个客户端连接
import hashlib  # 哈希算法库：把任意长度的数据"压缩"成固定长度的指纹（摘要），常用于安全存储密码 
import datetime


#记录各个ip失败登录次数的字典
FAILED_ATTEMPTS = {}

def recv_http_request(client_socket):
    """循环读取直到收完HTTP头部，再根据Content-Length读取body，返回 (headers_str, body_str)"""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = client_socket.recv(1024)
        if not chunk:
            break
        data += chunk

    if not data:
        return "", ""

    # 分离头部和body（body可能已部分读取）
    headers_raw, _, body_so_far = data.partition(b"\r\n\r\n")
    headers_str = headers_raw.decode('utf-8', errors='replace')
    body_bytes = body_so_far

    # 从头部提取Content-Length，补读剩余body
    content_length = 0
    for line in headers_str.splitlines():
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break

    remaining = content_length - len(body_bytes)
    while remaining > 0:
        chunk = client_socket.recv(min(1024, remaining))
        if not chunk:
            break
        body_bytes += chunk
        remaining -= len(chunk)

    return headers_str, body_bytes.decode('utf-8', errors='replace')

def handle_client(client_socket,client_address):
    print(f"\n召唤新线程,为{client_address}提供服务")
    try:
        # 循环读取直到收完完整的HTTP请求（头部+body）
        headers_part, body_part = recv_http_request(client_socket)
        if not headers_part:
             return
        
        #解析请求行
        request_lines = headers_part.splitlines()
        request_line = request_lines[0]
        print(f"\n收到请求行:{request_line}")
        
        method,path,version  = request_line.split(' ')
        client_ip = client_address[0]  # 提取客户端IP，整个函数通用

        #拦截POST 登录请求
        if method  == "POST" and path == '/login':
            print(f"拦截到POST提交的数据:{body_part}")

            #反爆破防御 检查该ip是否被已经被封禁
            if(FAILED_ATTEMPTS.get(client_ip,0))>=3:
                http_response = (
                    "HTTP/1.1 403 Forbidden\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    "\r\n"
                    "<h1 style='color:red;'>你的ip已被封禁!</h1>"
                    
                )
                client_socket.sendall(http_response.encode('utf-8'))
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[\033[36m{now}\033[0m] \033[31m[WARN]\033[0m {client_ip} | POST {path} | 403 Forbidden (已被封禁)")
                return

            # ========== 解析POST请求体 ==========
            # 此时 body_part 长这样: “username=admin&password=123456”
            # .split('&')  →  按 & 切开  →  [“username=admin”, “password=123456”]

            # params = {}  创建一个空字典（dict）
            params = {}

            for pair in body_part.split('&'):
                if '=' in pair:
                    # pair = “username=admin”
                    # .split('=') → [“username”, “admin”]
                    # k, v = [“username”, “admin”]  
                    k, v = pair.split('=')
                    params[k] = v

            # 循环结束后 params = {“username”: “admin”, “password”: “123456”}
            
            # ---------- 从字典中安全取值 ----------
            # .get(键, 默认值) → 如果"键"存在就返回对应的值，不存在则返回默认值
            # params.get('username', '')  →  字典里有"username"就返回其值，没有就返回空字符串''
            # 比 params['username'] 更安全，因为键不存在时不会报错（KeyError）
            user = params.get('username', '')
            pwd  = params.get('password', '')
            
            # hashlib —— 密码哈希验证 
            # hashlib.sha256(数据) → 创建一个SHA-256哈希对象
            #   SHA-256 是 SHA-2 家族的一员，输出固定 256 位（32 字节），不管输入多长
            # .encode('utf-8') → 把字符串转成字节串（bytes），因为哈希函数只接受字节
            # .hexdigest() → 把哈希结果转为 64 位的十六进制字符串（方便存储和比对）
            # 完整流程: "123456" → b"123456" → SHA256计算 → "8d969eef..."
            pwd_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

            # 这是 "123456" 的 SHA-256 哈希值（提前算好写死在代码里）
            # 哈希是单向的：知道哈希值无法反推出原始密码
            admin_real_hash = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"
            
            #登录检验
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if user == 'admin' and pwd_hash == admin_real_hash:
                result_html = f"<h1 style='color:green;'>登录成功！ 欢迎回来 {user}</h1>"
                print(f"[\033[36m{now}\033[0m] \033[32m[INFO]\033[0m {client_ip} | POST {path} | 200 OK (登录成功)")
            else:
                FAILED_ATTEMPTS[client_ip] = FAILED_ATTEMPTS.get(client_ip,0) +1
                attempts_left = 3- FAILED_ATTEMPTS[client_ip]
                result_html = f"<h1 style='color:red;'>登录失败 账号或密码错误 你还有{attempts_left}次机会</h1>"
                print(f"[\033[36m{now}\033[0m] \033[31m[WARN]\033[0m {client_ip} | POST {path} | 200 OK (登录失败 剩余{attempts_left}次)")
            
            # ---------- 构造 HTTP 响应 ----------
            # 先把 body 转成字节，拿到它的字节长度
            body_bytes = result_html.encode('utf-8')

            # Content-Length: 告诉客户端"响应体有多少字节"，客户端读完指定长度就停，不会傻等
            # Connection: close → 告诉客户端"我发完就关连接"，避免客户端尝试复用连接导致错乱
            http_response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode('utf-8') + body_bytes

            # sendall 发送整个响应（头部 + 正文）
            client_socket.sendall(http_response)
            return 
        
                    
                    
        #读取本地文件
        #路由安全边界转换 如果用户只访问根目录/ 默认指向/index.html
        if path == '/':
            path = "/index.html"
                    
        #防御目录穿越
        #获取白名单
        # os.getcwd() 获取当前工作目录（你运行脚本的文件夹路径），比如 D:\CTF_tools\web\Mini-HTTP-Server
        # os.path.join(a,b) 把两个路径拼在一起，自动处理 / 和 \ 的问题，比如 join("a","b") => "a\b"
        # os.path.abspath(路径) 把相对路径转成绝对路径，比如 "./www" => "D:\CTF_tools\web\Mini-HTTP-Server\www"
        base_dir = os.path.abspath(os.path.join(os.getcwd(),"www"))
                
        #拼接用户路径
        # path.lstrip('/') 去掉路径最左边的 / ，比如 "/index.html" => "index.html"
        # os.path.join(base_dir, path) 把白名单目录和用户请求路径拼在一起
        # os.path.abspath() 再次转成绝对路径，防止攻击者用 ../../ 之类的技巧跳出 www 目录（目录穿越攻击）
        request_path = os.path.abspath(os.path.join(base_dir,path.lstrip('/')))
        
        #判断真实路径 是否以base_dir开头
        if not request_path.startswith(base_dir):
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[\033[36m{now}\033[0m] \033[31m[WARN]\033[0m {client_ip} | GET {path} | 403 Forbidden (目录穿越攻击)")
            file_path  = "非法请求.txt"
        else:
            file_path = request_path
            print(f"正在尝试读取本地文件:{file_path}")
        
        #尝试打开文件
        try:
            #MIME类型与二进制传输
            #根据请求路径的后缀名（比如 .html, .jpg, .png），动态设置 Content-Type。这在网络协议中被称为 MIME 类型
            if file_path.endswith(".html") :
                content_type = "text/html; charset = utf-8"
            elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".css"):
                content_type = "text/css"
            else:
                #如果不认识告诉浏览器这是一个普通二进制流，默认下载
                content_type = "appliaction/octet-stream"
            #r只读模式 encoding="utf-8"保证中文不乱码 open(file_path,"r",encoding = "utf-8")
            #统一使用rb读取二进制模式打开文件
            with open(file_path,"rb") as f:
                file_content = f.read()
            
            response_header = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Type:{content_type}\r\n"
                f"Content-Length: {len(file_content)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            #拼接发送 因为此时的file_content 还是字节流
            #所以先把头部变为字节流
            final_response = response_header.encode('utf-8') + file_content
            client_socket.sendall(final_response)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[\033[36m{now}\033[0m] \033[32m[INFO]\033[0m {client_ip} | GET {path} | 200 OK")
        except FileNotFoundError:
            #如果文件不存在 返回404
            html_content = "<h1>404 Not Found</h1>"
            body_bytes = html_content.encode('utf-8')
            http_response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode('utf-8') + body_bytes
            client_socket.sendall(http_response)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[\033[36m{now}\033[0m] \033[33m[WARN]\033[0m {client_ip} | GET {path} | 404 Not Found")
                    
    except Exception as e:
        print(f"处理{client_address}时发生错误:{e}")
    finally:
        #这个线程服务完客户后 关闭连接 线程自动消亡
        client_socket.close()
        print(f"与{client_address}的连接已断开,释放线程")
            
        

def run_server():
    #1 创建Socket对象 IPv，TCP协议
    server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    
    #设置端口复用 避免关闭脚本再迅速重启时 系统提示Address already in use
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    
    #2 绑定IP和端口
    HOST = '127.0.0.1'
    PORT = 8081
    server_socket.bind((HOST,PORT))
    
    #3开始监听端口 5表示操作系统允许挂起的最大未接受连接数
    server_socket.listen(5)
    print(f"服务器正在监听 http://{HOST}:{PORT}..\n")
    
    try:
        #服务器通常是个死循环，不断等待新的客户端进来
        while True:
                #4 阻塞并等待连接 如果没有客户端发请求，程序会一直卡在这里
                #一旦有连接，accept()会返回一个新的socket专门用于和这个客户端通信以及客户端的地址
                client_socket,client_address = server_socket.accept()
                print(f"收到来自{client_address}的连接")
                
                # 创建一个子线程去处理这个客户端
                # target=  指定线程要执行的函数
                # args=    传给 target 函数的参数（以元组形式）
                client_thread = threading.Thread(
                    target = handle_client,
                    args=(client_socket,client_address)

                )

                # 设为守护线程：主线程退出时，守护线程自动被销毁，不等它执行完
                client_thread.daemon = True

                # start() 启动线程 → 内部调用 handle_client(client_socket, client_address)
                # 主线程不等待，立刻回到 while 循环继续 accept 下一个连接
                client_thread.start()
                    
    except KeyboardInterrupt:
        #捕获ctrl+c 退出
        print("\n 正在关闭服务器...")
    finally:
        server_socket.close()
        
if __name__=='__main__':
    run_server()