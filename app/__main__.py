"""命令行入口：run / doctor。"""

from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from .config import APP_NAME, APP_VERSION, AppConfig, Paths, resolve_data_dir
from .netinfo import list_local_ipv4


def _configure_stdio() -> None:
    """在 Windows GBK 控制台/重定向管道下避免 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _normalize_argv(argv: list[str]) -> list[str]:
    """允许省略 run 子命令：`app --open-admin` 等价于 `app run --open-admin`。"""
    if not argv:
        return ["run"]
    if argv[0] in {"-h", "--help"}:
        return argv
    if argv[0].startswith("-"):
        return ["run", *argv]
    return argv


def _print_banner(bind_host: str, port: int, serve_on_lan: bool, data_dir: Path) -> None:
    print("=" * 64)
    print(f"  {APP_NAME} v{APP_VERSION}  —  DeepSeek 网页 → 本地 OpenAI API")
    print("=" * 64)
    print(f"  API 地址   : http://127.0.0.1:{port}/v1")
    if serve_on_lan:
        ips = list_local_ipv4()
        for ip in ips:
            print(f"             : http://{ip}:{port}/v1   (局域网)")
        if not ips:
            print("             : (未检测到局域网 IPv4 地址)")
    else:
        print("             : 局域网服务未开启（设置页可开启，需重启服务）")
    print("  模型名称   : deepseek-web（可在设置页查看）")
    # 本机访问设置页无需令牌，因此这里直接打印可点击的地址
    print(f"  设置页     : http://127.0.0.1:{port}/admin/    (仅本机可访问)")
    print(f"  监听地址   : {bind_host}:{port}")
    print(f"  数据目录   : {data_dir}")
    print("  停止服务   : Ctrl+C（后台运行时用 scripts\\stop.ps1）")
    print("=" * 64, flush=True)


def command_run(args: argparse.Namespace) -> int:
    import uvicorn

    from .main import create_app

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else resolve_data_dir()
    paths = Paths(data_dir)
    paths.ensure()
    config = AppConfig.load(paths.config_path)
    if args.host:
        config.host = args.host
    if args.port:
        config.port = int(args.port)
    if args.log_level:
        config.log_level = args.log_level
    if args.no_browser:
        config.launch_browser_on_start = False

    bind_host = "0.0.0.0" if config.serve_on_lan else config.host
    paths.pid_path.write_text(str(os.getpid()), encoding="utf-8")
    app = create_app(config, paths)
    admin_url = f"http://127.0.0.1:{config.port}/admin/"
    _print_banner(bind_host, config.port, config.serve_on_lan, paths.data_dir)
    if args.open_admin:
        threading.Timer(1.5, lambda: webbrowser.open(admin_url)).start()
    try:
        uvicorn.run(app, host=bind_host, port=config.port, log_level="warning", access_log=False)
    finally:
        try:
            paths.pid_path.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else resolve_data_dir()
    paths = Paths(data_dir)
    ok = True

    print(f"{APP_NAME} doctor v{APP_VERSION}")
    print(f"平台       : {platform.platform()} ({platform.machine()})")
    print(f"Python     : {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 10):
        print("  ✗ 需要 Python 3.10 及以上")
        ok = False
    else:
        print("  ✓ 版本满足要求")

    try:
        import playwright  # noqa: F401

        print("  ✓ playwright 已安装")
    except ImportError:
        print("  ✗ playwright 未安装（pip install -r requirements.txt）")
        ok = False

    try:
        from .bridge.deepseek import bundled_chromium_available, find_browser

        found = find_browser()
        if found:
            print(f"  ✓ 浏览器：{found[0]} ({found[1]})")
        elif bundled_chromium_available():
            print("  ✓ 未找到 Edge/Chrome，但检测到 Playwright 自带 Chromium，可直接使用")
        else:
            print(
                "  ✗ 未找到浏览器：请安装 Microsoft Edge / Google Chrome，"
                "或运行 `python -m playwright install chromium`"
            )
            ok = False
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 浏览器检测失败：{exc}")
        ok = False

    try:
        paths.ensure()
        probe = paths.data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"  ✓ 数据目录可写：{paths.data_dir}")
    except OSError as exc:
        print(f"  ✗ 数据目录不可写：{exc}")
        ok = False

    config_path = paths.config_path
    if config_path.exists():
        config = AppConfig.load(config_path)
        # 用连接测试判断端口（Windows 上 SO_REUSEADDR 会让 bind 误判为可用）
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                in_use = sock.connect_ex(("127.0.0.1", config.port)) == 0
            except OSError:
                in_use = False
        if in_use:
            print(f"  ! 端口 {config.port} 已被占用（服务可能已在运行）")
        else:
            print(f"  ✓ 端口 {config.port} 可用")
        ips = list_local_ipv4()
        if ips:
            print(f"  ✓ 局域网地址：{', '.join(ips)}")
        else:
            print("  ! 未检测到局域网 IPv4 地址（仅本机可用）")
        state = "已开启" if config.serve_on_lan else "未开启（设置页可开启，需重启服务）"
        print(f"  ✓ 在网络中提供服务：{state}")
        print(f"  ✓ 配置文件：{config_path}")
    else:
        print(f"  ! 配置文件尚未创建（首次运行 run 时自动生成）：{config_path}")

    print("结论：" + ("环境正常，可以运行。" if ok else "存在问题，请先修复上面的 ✗ 项。"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    arguments = _normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(prog="deepseek-local-bridge")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="启动本地服务")
    run_parser.add_argument("--host", default=None, help="监听地址（默认 127.0.0.1）")
    run_parser.add_argument("--port", type=int, default=None, help="监听端口（默认 8317）")
    run_parser.add_argument("--data-dir", default=None, help="数据目录")
    run_parser.add_argument("--open-admin", action="store_true", help="启动后自动打开设置页")
    run_parser.add_argument("--no-browser", action="store_true", help="启动时不自动打开浏览器")
    run_parser.add_argument("--log-level", default=None, help="日志级别")
    run_parser.set_defaults(func=command_run)

    doctor_parser = subparsers.add_parser("doctor", help="环境自检")
    doctor_parser.add_argument("--data-dir", default=None, help="数据目录")
    doctor_parser.set_defaults(func=command_doctor)

    args = parser.parse_args(arguments)
    result = args.func(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
