"""本机网络信息：枚举可用的局域网 IPv4 地址。"""

from __future__ import annotations

import socket


def list_local_ipv4() -> list[str]:
    """返回局域网 IPv4 地址列表（不含 127.*），192.168.* 优先。"""
    found: list[str] = []

    def usable(ip: str) -> bool:
        # 过滤回环、APIPA 链路本地（169.254.*）以及代理软件 TUN 网卡常用的保留网段（198.18/15）
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            return False
        if ip.startswith("198.18.") or ip.startswith("198.19."):
            return False
        return True

    def add(ip: str) -> None:
        if usable(ip) and ip not in found:
            found.append(ip)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.3)
            sock.connect(("223.5.5.5", 80))
            add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass

    def rank(ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10."):
            return (1, ip)
        if ip.startswith("172."):
            return (2, ip)
        return (3, ip)

    return sorted(found, key=rank)
