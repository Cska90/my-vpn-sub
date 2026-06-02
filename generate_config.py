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

def parse_vless_link(link):
    link = link.strip()
    if not link.startswith("vless://"):
        return None
    try:
        # Извлекаем fragment (имя) до очистки, чтобы не потерять пробелы
        name = "VLESS_PROXY"
        if "#" in link:
            link, fragment = link.split("#", 1)
            name = urllib.parse.unquote(fragment).strip()

        # Пакуем обратно плюс, если он превратился в пробел
        link = link.replace(" ", "+")

        # Находим UUID, сервер и порт регуляркой напрямую
        match = re.match(r"vless://([^@]+)@([^:]+):(\d+)", link)
        if not match:
            return None
            
        uuid_str = match.group(1).strip()
        server = match.group(2).strip()
        port = int(match.group(3).strip())

        # Ищем параметры внутри ссылки через простые регулярки (так надежнее всего)
        pbk_match = re.search(r"[?&][Pp][Bb][Kk]=([^&]+)", link)
        sid_match = re.search(r"[?&][Ss][Ii][Dd]=([^&]+)", link)
        sni_match = re.search(r"[?&][Ss][🇳🇳][🇮🇮]=([^&]+)", link, re.IGNORECASE) # на всякий случай sni
        type_match = re.search(r"[?&][🇹🇹][🇾🇾][🇵🇵][🇪🇪]=([^&]+)", link, re.IGNORECASE)
        fp_match = re.search(r"[?&][🇫🇫][🇵🇵]=([^&]+)", link, re.IGNORECASE)
        sname_match = re.search(r"[?&]servicename=([^&]+)", link, re.IGNORECASE)
        path_match = re.search(r"[?&]path=([^&]+)", link, re.IGNORECASE)

        public_key = pbk_match.group(1).strip() if pbk_match else ""
        short_id = sid_match.group(1).strip() if sid_match else ""
        sni = sni_match.group(1).strip() if sni_match else server
        network = type_match.group(1).strip() if type_match else "tcp"
        fp = fp_match.group(1).strip() if fp_match else "chrome"

        # Исправляем возможные косяки форматирования ключа (заменяем ломающие символы обратно)
        if "_" in public_key or "-" in public_key:
            public_key = public_key.replace("_", "/").replace("-", "+")

        proxy = {
            "name": name.replace(":", "-"),
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": uuid_str,
            "tls": True,
            "udp": True,
            "network": network,
            "servername": sni,
            "reality-opts": {
                "public-key": public_key,
                "short-id": short_id
            },
            "client-fingerprint": fp
        }

        if network == "grpc":
            sname = sname_match.group(1).strip() if sname_match else ""
            proxy["grpc-opts"] = {"grpc-service-name": sname}
        elif network == "ws":
            path = path_match.group(1).strip() if path_match else "/"
            proxy["ws-opts"] = {"path": path}

        return proxy
    except Exception as e:
        print(f"Ошибка: {e}")
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
        print("Ссылок нет, создаем DIRECT")
        proxies.append({
            "name": "DIRECT_ЗАГЛУШКА",
            "type": "vless",
            "server": "127.0.0.1",
            "port": 443,
            "uuid": "00000000-0000-0000-0000-000000000000",
            "tls": False,
            "udp": True,
            "network": "tcp"
        })

    # Убираем дубли имён
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
        
    print("Конфиг собран в мягком режиме!")

if __name__ == "__main__":
    main()
    
