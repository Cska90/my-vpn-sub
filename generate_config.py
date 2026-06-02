import os
import urllib.parse
import yaml

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

def parse_vless_link(link):
    link = link.strip()
    if not link.startswith("vless://"):
        return None
    try:
        url_parts = urllib.parse.urlparse(link)
        user_info = url_parts.username
        
        server_netloc = url_parts.netloc.split('@')[-1]
        if ':' in server_netloc:
            server, port = server_netloc.split(':')
            port = int(port)
        else:
            server = server_netloc
            port = 443
        
        name = urllib.parse.unquote(url_parts.fragment) if url_parts.fragment else f"VLESS_{server}_{port}"
        query = urllib.parse.parse_qs(url_parts.query)
        
        query_lower = {k.lower(): v for k, v in query.items()}
        public_key = query_lower.get("pbk", [""])[0]
        short_id = query_lower.get("sid", [""])[0]
        
        # СТРОГАЯ ПРОВЕРКА КЛЮЧА REALITY
        # 1. Длина должна быть не меньше 40 символов
        # 2. Ключ не должен содержать некорректные символы вроде '_' или '-' (частая ошибка кривых ссылок)
        if len(public_key) < 40 or "_" in public_key or "-" in public_key:
            print(f"Ссылка '{name}' ИГНОРИРУЕТСЯ: обнаружен невалидный Reality public key.")
            return None
            
        proxy = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": user_info,
            "tls": True,
            "udp": True,
            "network": query_lower.get("type", ["tcp"])[0],
            "servername": query_lower.get("sni", [server])[0],
            "reality-opts": {
                "public-key": public_key,
                "short-id": short_id
            },
            "client-fingerprint": query_lower.get("fp", ["chrome"])[0]
        }
        
        if proxy["network"] == "grpc":
            proxy["grpc-opts"] = {"grpc-service-name": query_lower.get("servicename", [""])[0]}
        elif proxy["network"] == "ws":
            proxy["ws-opts"] = {"path": query_lower.get("path", ["/"])[0]}
            
        return proxy
    except Exception as e:
        print(f"Ошибка парсинга ссылки: {e}")
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
        
    print("Конфиг успешно очищен от плохих ключей!")

if __name__ == "__main__":
    main()
    
