"""
proxy_manager.py  –  Tự động tải, kiểm tra & xoay Free Proxy live cho Zefoy Bot
"""

import os
import random
import requests as req_basic
from curl_cffi import requests

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/data/http.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=all"
]

def fetch_all_free_proxies():
    """Tải toàn bộ danh sách Proxy Free từ các nguồn GitHub & API."""
    all_proxies = set()
    print("[+] [Proxy Manager] Dang tai danh sach Free Proxy moi nhat tu GitHub...")
    for source in PROXY_SOURCES:
        try:
            res = req_basic.get(source, timeout=6)
            if res.status_code == 200:
                lines = res.text.strip().splitlines()
                for line in lines:
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        all_proxies.add(line)
        except Exception:
            pass
            
    proxy_list = list(all_proxies)
    random.shuffle(proxy_list)
    print(f"[+] [Proxy Manager] Da thu thap {len(proxy_list)} Free Proxy IPs!")
    return proxy_list

def get_working_proxy(max_checks=25, test_url="https://zefoy.com"):
    """Tự động quét test nhanh các Free Proxies để chọn IP hoạt động tốt (200 OK)."""
    proxies = fetch_all_free_proxies()
    if not proxies:
        print("[!] Khong lay duoc proxy, su dung Direct IP mac dinh.")
        return None

    print(f"[*] [Proxy Manager] Dang test toc do ngau nhien {max_checks} Free Proxies...")
    for p in proxies[:max_checks]:
        proxy_url = f"http://{p}"
        try:
            r = requests.get(
                test_url, 
                proxies={"http": proxy_url, "https": proxy_url}, 
                timeout=4, 
                impersonate="chrome120"
            )
            if r.status_code == 200:
                print(f"[+] [Proxy Manager] TIM THAY PROXY SONG SAN SANG: {p}")
                return p
        except Exception:
            pass

    print("[!] Khong tim thay Free Proxy dat phan hoi duoi 4s, su dung Direct IP.")
    return None

if __name__ == "__main__":
    p = get_working_proxy()
    print("Free Proxy được chọn:", p)
