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
    """Dùng Direct IP (đã tắt xoay Proxy theo yêu cầu)."""
    print("[+] [Proxy Manager] Da TAT Proxy, dang su dung Direct IP.")
    return None

if __name__ == "__main__":
    p = get_working_proxy()
    print("Free Proxy được chọn:", p)
