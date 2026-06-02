import os
import urllib.parse
import yaml
import re

BASE_CONFIG = {
    "port": 7890,
    "socks-port": 7891,
    "allow-lan": True,
    "mode": "rule",
    "log-level": "info",
    "ipv6": False,
    "dns": {
        "enable": True,
        "listen": "0.0.0.0:5353",
        "ipv6": False,
        "enhanced-mode": "fake-ip",
        "fake-ip-range": "198.18.0.1/16",
        "default-nameserver": ["114.114.114.114", "8.8.8.8"],
        "nameserver": ["https://doh.pub/dns-query", "https://dns.google/dns-query"]
    }
}

def is_valid_uuid(uuid_str):
    # Проверяем стандартный формат UUID (8-4-4-4-12 шестнадцатеричных символов)
    return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", uuid_str))

def is_valid_base64_pbk(pbk):
    # Ключ Reality должен быть от 40 до 50 символов и содержать ТОЛЬКО символы Base64
    if not pbk or len(pbk) < 40 or len(pbk) > 50:
        return False
    return bool(re.match(r"^[A-Za-z0-9+/=]+$", pbk))

def parse_vless_link(link):
    link = link.strip()
    if not link.startswith("vless://"):
        return None
    try:
        url_parts = urllib.parse.urlparse(link)
        user_info = url_parts.username
        
        # Жесткая проверка UUID
        if not user_info or not is_valid_uuid(user_info.strip()):
            print(f"Ссылка пропущена: неверный формат UUID.")
            return None
            
        server_netloc = url_parts.netloc.split('@')[-1]
        if '?' in server_netloc:
            server_netloc = server_netloc.split('?')[0]
            
        if ':' in server_netloc:
            server, port = server_netloc.split(':')
            try:
                port = int(port)
            except:
                return None
        else:
            server = server_netloc
            port = 443
            
        server = server.strip()
        if not server:
            return None
        
        name = urllib.parse.unquote(url_parts.fragment) if url_parts.fragment else f"VLESS_{server}_{port}"
        name = name.strip().replace(":", "-") # убираем двоеточия из имён, Clash их не любит
        
        query = urllib.parse.parse_qs(url_parts.query)
        query_lower = {k.lower(): v for k, v in query.items()}
        
        public_key = query_lower.get("pbk", [""])[0].strip()
        short_id = query_lower.get("sid", [""])[0].strip()
        sni = query_lower.get("sni", [server])[0].strip()
        
        # Тотальная фильтрация Reality ключа
        if not is_valid_base64_pbk(public_key):
            print(f"Ссылка '{name}' ЗАБРАКОВАНА: неверный Reality public key (pbk).")
            return None
            
        proxy = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": user_info.strip(),
            "tls": True,
            "udp": True,
            "network": query_lower.get("type", ["tcp"])[0].strip(),
            "servername": sni,
            "reality-opts": {
                "public-key": public_key,
                "short-id": short_id
            },
            "client-fingerprint": query_lower.get("fp", ["chrome"])[0].strip()
        }
        
        if proxy["network"] == "grpc":
            proxy["grpc-opts"] = {"grpc-service-name": query_lower.get("servicename", [""])[0].strip()}
        elif proxy["network"] == "ws":
            proxy["ws-opts"] = {"path": query_lower.get("path", ["/"])[0].strip()}
            
        return proxy
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

def main():
    sub_file = "sub.txt"
    output_file = "config.yaml"
    
    links = []
    if os.path.exists(sub_file):
        with open(sub_file, "r", encoding="utf-8") as f:
            links = f.readlines()
        
    proxies = []
    for link in links:
        if link.strip() and not link.startswith("#"):
            proxy = parse_vless_link(link)
            if proxy:
                proxies.append(proxy)
                
    if not proxies:
        proxies.append({
            "name": "Временная заглушка DIRECT",
            "type": "vless",
            "server": "127.0.0.1",
            "port": 443,
            "uuid": "00000000-0000-0000-0000-000000000000",
            "tls": False,
            "udp": True,
            "network": "tcp"
        })

    # Убираем дубликаты имён, если они есть
    seen_names = set()
    unique_proxies = []
    for p in proxies:
        if p["name"] not in seen_names:
            seen_names.add(p["name"])
            unique_proxies.append(p)
    proxies = unique_proxies

    proxy_names = [p["name"] for p in proxies]
    
    proxy_groups = [
        {"name": "🚀 AUTO", "type": "url-test", "proxies": proxy_names, "url": "http://cp.cloudflare.com/generate_204", "interval": 300, "tolerance": 50},
        {"name": "🤖 AI", "type": "select", "proxies": ["🚀 AUTO"] + proxy_names + ["DIRECT"]},
        {"name": "🎬 MEDIA", "type": "select", "proxies": ["🚀 AUTO"] + proxy_names + ["DIRECT"]},
        {"name": "💬 SOCIAL", "type": "select", "proxies": ["🚀 AUTO"] + proxy_names + ["DIRECT"]},
        {"name": "🛡 VPN", "type": "select", "proxies": ["🚀 AUTO"] + proxy_names + ["DIRECT"]},
        {"name": "🌐 DIRECT", "type": "select", "proxies": ["DIRECT", "🚀 AUTO"]}
    ]
    
    rules = [
        "DOMAIN-KEYWORD,openai,🤖 AI",
        "DOMAIN-KEYWORD,anthropic,🤖 AI",
        "DOMAIN-KEYWORD,claude,🤖 AI",
        "DOMAIN-SUFFIX,chatgpt.com,🤖 AI",
        "DOMAIN-KEYWORD,youtube,🎬 MEDIA",
        "DOMAIN-SUFFIX,googlevideo.com,🎬 MEDIA",
        "DOMAIN-SUFFIX,netflix.com,🎬 MEDIA",
        "DOMAIN-SUFFIX,telegram.org,💬 SOCIAL",
        "DOMAIN-SUFFIX,telegram.me,💬 SOCIAL",
        "DOMAIN-SUFFIX,t.me,💬 SOCIAL",
        "DOMAIN-SUFFIX,whatsapp.com,💬 SOCIAL",
        "DOMAIN-SUFFIX,whatsapp.net,💬 SOCIAL",
        "DOMAIN-KEYWORD,instagram,💬 SOCIAL",
        "DOMAIN-KEYWORD,facebook,💬 SOCIAL",
        "DOMAIN-KEYWORD,tiktok,💬 SOCIAL",
        "DOMAIN-SUFFIX,twitter.com,💬 SOCIAL",
        "DOMAIN-SUFFIX,x.com,💬 SOCIAL",
        "DOMAIN-SUFFIX,4pda.to,🛡 VPN",
        "DOMAIN-SUFFIX,4pda.ru,🛡 VPN",
        "DOMAIN-SUFFIX,rutracker.org,🛡 VPN",
        "DOMAIN-SUFFIX,rutor.info,🛡 VPN",
        "DOMAIN-SUFFIX,rutor.org,🛡 VPN",
        "DOMAIN-KEYWORD,nnmclub,🛡 VPN",
        "MATCH,🌐 DIRECT"
    ]
    
    config = BASE_CONFIG.copy()
    config["proxies"] = proxies
    config["proxy-groups"] = proxy_groups
    config["rules"] = rules
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        
    print("КОНФИГ ТОТАЛЬНО ЗАЩИЩЕН!")

if __name__ == "__main__":
    main()
    
