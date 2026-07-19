import os
import time
import sys
import platform
from datetime import datetime, timedelta

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

def clear_screen():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def get_uptime():
    if HAS_PSUTIL:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
    else:
        try:
            import subprocess
            result = subprocess.run(['uptime'], capture_output=True, text=True)
            return result.stdout.strip()
        except Exception:
            return "Uptime information unavailable"
    return format_uptime(uptime_seconds)

def format_uptime(seconds):
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"

def get_cpu_usage():
    if HAS_PSUTIL:
        return f"{psutil.cpu_percent(interval=1)}%"
    return "N/A"

def get_memory_info():
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        return f"Total: {mem.total / (1024**3):.1f} GB | Used: {mem.used / (1024**3):.1f} GB | {mem.percent}%"
    return "N/A"

def get_disk_info():
    if HAS_PSUTIL:
        disk = psutil.disk_usage('/')
        return f"Total: {disk.total / (1024**3):.1f} GB | Used: {disk.used / (1024**3):.1f} GB | {disk.percent}%"
    return "N/A"

def get_network_info():
    if HAS_PSUTIL:
        net = psutil.net_io_counters()
        sent_mb = net.bytes_sent / (1024**2)
        recv_mb = net.bytes_recv / (1024**2)
        return f"Sent: {sent_mb:.1f} MB | Recv: {recv_mb:.1f} MB"
    return "N/A"

def get_process_count():
    if HAS_PSUTIL:
        return psutil.pids()
    return "N/A"

def print_dashboard():
    clear_screen()
    print("=" * 60)
    print("           🚀 SYSTEM MONITOR DASHBOARD 🚀")
    print("=" * 60)
    print(f"  Hostname:     {platform.node()}")
    print(f"  OS:           {platform.system()} {platform.release()}")
    print(f"  Python:       {platform.python_version()}")
    print(f"  Last Update:  {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 60)
    print(f"  ⏱️  UPTIME:     {get_uptime()}")
    print(f"  🖥️  CPU:        {get_cpu_usage()}")
    print(f"  💾 MEMORY:    {get_memory_info()}")
    print(f"  💿 DISK:      {get_disk_info()}")
    print(f"  🌐 NETWORK:   {get_network_info()}")
    if HAS_PSUTIL:
        print(f"  📊 PROCESSES: {len(psutil.pids())}")
    print("=" * 60)

def main():
    print("🚀 Iniciando Monitor de Sistema...")
    print("Pressione Ctrl+C para sair")
    try:
        while True:
            print_dashboard()
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n👋 Monitor encerrado!")
        sys.exit(0)

if __name__ == "__main__":
    main()