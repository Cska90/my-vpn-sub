import os
import urllib.parse
import yaml
import re
import base64

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
    return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", uuid_str))

def clean_and_validate_pbk(pbk):
    if not pbk:
        return None
    
    # Декодирование URL может превратить '+' в пробел. Исправляем этот частый баг:
    pbk = pbk.strip().replace(" ", "+")
    
    # Базовая проверка длины и символов
    if len(pbk) < 40 or len(pbk) > 50:
        return None
    if not re.match(r"^[A-Za-z0-9+/=]+$", pbk):
        return None
        
    # КРИТИЧЕСКИЙ ТЕСТ: Проверяем, декодируется ли строка стандартным Base64.
    # Если внутри кривая контрольная сумма, b64decode вызовет ошибку.
    try:
        # Добавляем паддинг '=', если его не хватает для кратности 4
        padded_pbk = pbk + "=" * ((4 - len(pbk) % 4) % 4)
        base64.b64decode(padded_pbk, validate=True)
        return pbk # Ключ идеален
    except Exception:
        return None # Ключ невалиден

def parse_vless_link(link):
    link = link.strip()
    if not link.startswith("vless://"):
        return None
    try:
        url_parts = urllib.parse.urlparse(link)
        user_info = url_parts.username
        
        if not user_info or not is_valid_uuid(user_info.strip()):
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
        name = name.strip().replace(":", "-")
        
        query = urllib.parse.parse_qs(url_parts.query)
        query_lower = {k.lower(): v for k, v in query.items()}
        
        raw_pbk = query_lower.get("pbk", [""])[0]
        public_key = clean_and_validate_pbk(raw_pbk)
        
        # Если ключ не прошёл глубокую проверку — отбраковываем сервер
        if not public_key:
            print(f"Ссылка '{name}' ЗАБРАКОВАНА: не прошёл валидацию Base64 Reality public key.")
            return None
            
        short_id = query_lower.get("sid", [""])[0].strip()
        sni = query_lower.get("sni", [server])[0].strip()
        
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
        
    print("ГЛУБОКАЯ ДЕКОД-ВАЛИДАЦИЯ ЗАВЕРШЕНА!")

if __name__ == "__main__":
    main()
    
