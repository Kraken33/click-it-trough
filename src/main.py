import logging
import os
import sys
import time
import typer
import uvicorn
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="TikTok iOS Automation Suite - MacBook Controller")
console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@app.command()
def doctor(
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file")
):
    """
    Runs comprehensive diagnostics: Xcode, USB devices, WDA status, and Vision OCR.
    """
    console.print(Panel.fit("[bold cyan]TikTok iOS Automation - System Diagnostics[/bold cyan]"))

    table = Table(title="Diagnostic Checks")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # 1. Check Python & Platform
    table.add_row("Operating System", "✅ macOS", sys.platform)
    table.add_row("Python Runtime", "✅ Active", sys.version.split()[0])

    # 2. Check Xcode
    import shutil
    has_xcode = shutil.which("xcodebuild") is not None
    if has_xcode:
        table.add_row("Xcode CLI Tools", "✅ Installed", "/usr/bin/xcodebuild")
    else:
        table.add_row("Xcode CLI Tools", "❌ Missing", "Install via Xcode or xcode-select --install")

    # 3. Check Apple Vision OCR
    try:
        from src.vision.ocr import VisionOCR
        ocr = VisionOCR()
        if ocr._has_vision:
            table.add_row("Apple Vision OCR", "✅ Native Active", "Hardware-accelerated Apple Vision")
        else:
            table.add_row("Apple Vision OCR", "⚠️ Fallback", "Running without native Vision")
    except Exception as e:
        table.add_row("Apple Vision OCR", "❌ Error", str(e))

    # 4. Check USB Device & WDA
    try:
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        from src.bridge.device_manager import DeviceManager
        mgr = DeviceManager(wda_url=cfg.get("device", {}).get("wda_url", "http://localhost:8100"))
        status = mgr.check_connection()

        usb_count = status.get("usb_devices_count", 0)
        if usb_count > 0:
            dev_str = ", ".join([d.get("udid", "")[:12] + "..." for d in status.get("usb_devices", [])])
            table.add_row("USB iPhone Connection", f"✅ Found {usb_count} Device(s)", dev_str)
        else:
            table.add_row("USB iPhone Connection", "⚠️ No Devices Detected", "Plug in iPhone and unlock")

        if status.get("wda_alive"):
            sz = status.get("screen_size", {})
            table.add_row("WebDriverAgent (WDA)", "✅ Online & Ready", f"Port 8100 ({sz.get('width')}x{sz.get('height')} pt)")
        else:
            table.add_row("WebDriverAgent (WDA)", "❌ Offline (Port 8100)", "Run ./scripts/start_tunnel.sh")
    except Exception as e:
        table.add_row("Device Bridge", "❌ Error", str(e))

    console.print(table)


def get_app():
    from src.web.app import create_app
    return create_app()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind"),
    port: int = typer.Option(8000, help="Port to listen on"),
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload on code changes"),
):
    """
    Starts the FastAPI server and WebSocket backend for the React Web Dashboard.
    """
    console.print(f"[bold green]Starting TikTok Automation Server on http://{host}:{port}[/bold green]")
    if reload:
        uvicorn.run("src.main:get_app", host=host, port=port, reload=True, factory=True, log_level="info")
    else:
        from src.web.app import create_app
        web_app = create_app(config_path=config_file)
        uvicorn.run(web_app, host=host, port=port, log_level="info")


@app.command()
def test_touch(
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file")
):
    """
    Tests biometric Bézier curve gestures and double-tap like on the connected iPhone.
    """
    console.print("[cyan]Connecting to device for touch test...[/cyan]")
    with open(config_file, "r") as f:
        cfg = yaml.safe_load(f)

    from src.bridge.wda_client import WDAClient
    from src.physics.gesture import BiometricGestureEngine

    client = WDAClient(base_url=cfg.get("device", {}).get("wda_url", "http://localhost:8100"))
    if not client.is_alive():
        console.print("[bold red]❌ WebDriverAgent is not reachable on localhost:8100[/bold red]")
        console.print("Ensure your iPhone is connected and ./scripts/start_tunnel.sh is running.")
        raise typer.Exit(1)

    w, h = client.get_window_size()
    console.print(f"Screen size: {w}x{h} pt")
    engine = BiometricGestureEngine(client=client, screen_width=w, screen_height=h)

    console.print("Executing biometric upward swipe (Bézier arc)...")
    engine.swipe_next_video()
    time.sleep(2)

    console.print("Executing authentic double-tap like...")
    engine.double_tap_like()
    console.print("[bold green]✅ Touch test completed successfully![/bold green]")


@app.command()
def warm(
    duration: int = typer.Option(15, help="Session duration in minutes"),
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file"),
):
    """
    Runs a headless TikTok warming session directly from the terminal.
    """
    with open(config_file, "r") as f:
        cfg = yaml.safe_load(f)

    from src.engine.session_runner import SessionRunner
    runner = SessionRunner(config=cfg)

    console.print(f"[bold green]Starting {duration}-minute headless warming session...[/bold green]")
    runner.start(duration_minutes=duration)

    try:
        while runner.stats.state == "RUNNING":
            s = runner.stats
            console.print(
                f"[dim]{s.duration_seconds}s[/dim] | "
                f"Videos: [bold cyan]{s.videos_watched}[/bold cyan] | "
                f"Likes: [bold red]{s.likes_count}[/bold red] | "
                f"Action: [yellow]{s.current_action}[/yellow]"
            )
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping session...[/yellow]")
        runner.stop()

    console.print("[bold green]Session completed.[/bold green]")


@app.command()
def test_screen(
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file"),
    recover: bool = typer.Option(False, "--recover", "-r", help="Automatically attempt recovery to FYP if not on feed"),
):
    """
    Analyzes the current iPhone screen: detects interface type (feed, likes list, comments,
    shop, sound, camera, live, profile, search, wrong tab, popup, homescreen) and tests recovery.
    """
    with open(config_file, "r") as f:
        cfg = yaml.safe_load(f)

    from src.bridge.device_manager import DeviceManager
    from src.vision.detector import ScreenDetector
    from src.vision.ocr import VisionOCR

    console.print(Panel.fit("[bold cyan]Screen Interface Analysis & Diagnostics[/bold cyan]"))
    mgr = DeviceManager(wda_url=cfg.get("device", {}).get("wda_url", "http://localhost:8100"))
    screen = mgr.get_screen()
    if not screen:
        console.print("[bold red]❌ Could not capture screen from device. Ensure WDA is running.[/bold red]")
        raise typer.Exit(1)

    ocr = VisionOCR()
    detector = ScreenDetector(ocr)

    state, markers = detector.detect_screen_state(screen)
    metrics = detector.extract_sidebar_metrics(screen)

    table = Table(title="Screen Detection Result")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Detected State", f"[bold green]{state}[/bold green]" if state == "feed" else f"[bold yellow]{state}[/bold yellow]")
    table.add_row("Matched Markers", ", ".join(markers) if markers else "[dim]None[/dim]")
    table.add_row("Sidebar Metrics", str(metrics) if metrics else "[dim]None detected[/dim]")
    console.print(table)

    if state == "feed":
        console.print("[bold green]✅ Screen is already on clean FYP video feed.[/bold green]")
        return

    if recover:
        console.print(f"[yellow]Executing return-to-FYP recovery from state '{state}'...[/yellow]")
        from src.engine.session_runner import SessionRunner
        runner = SessionRunner(config=cfg, device_manager=mgr)
        ok, final_state = runner.recover_to_feed(max_attempts=3)
        if ok:
            console.print(f"[bold green]✅ Successfully recovered to FYP video feed (state='{final_state}')![/bold green]")
        else:
            console.print(f"[bold red]❌ Recovery failed: remaining state is '{final_state}'[/bold red]")


@app.command()
def recover_now(
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file"),
):
    """
    Executes immediate recovery from any screen/interface back to the clean TikTok FYP feed.
    """
    test_screen(config_file=config_file, recover=True)


@app.command()
def test_live_recovery(
    config_file: str = typer.Option("config/default_config.yaml", help="Path to config file"),
):
    """
    Runs automated on-phone test: opens all key TikTok interfaces (comments, keyboard,
    share sheet, profile, search, camera, tabs, sound) and verifies recovery to FYP.
    """
    from tests.test_live_phone_recovery import LivePhoneRecoveryTester
    tester = LivePhoneRecoveryTester(config_path=config_file)
    if not tester.check_prerequisites():
        raise typer.Exit(1)
    tester.run_all_interface_tests()


if __name__ == "__main__":
    app()
