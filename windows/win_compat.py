import os
import sys
import subprocess

def setup_windows_terminal():
    """Habilita suporte a sequências ANSI no terminal do Windows (CMD/PowerShell)."""
    if os.name == 'nt':
        try:
            from ctypes import windll, wintypes
            kernel32 = windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            hStdOut = kernel32.GetStdHandle(-11)
            mode = wintypes.DWORD()
            kernel32.GetConsoleMode(hStdOut, wintypes.BYREF(mode))
            kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004)
        except Exception:
            # Se falhar, o Rich geralmente consegue lidar com isso sozinho, 
            # mas essa é uma camada extra de segurança.
            pass

def get_windows_shell():
    """Retorna o shell apropriado para o Windows."""
    if os.name == 'nt':
        return "powershell.exe" if shutil.which("powershell.exe") else "cmd.exe"
    return None

def fix_path(path):
    """Corrige caminhos para o formato do Windows se necessário."""
    if os.name == 'nt':
        return path.replace('/', '\\')
    return path

def run_win_command(command):
    """Executa um comando de forma compatível com o shell do Windows."""
    if os.name == 'nt':
        # No Windows, usamos shell=True para comandos internos do CMD/PowerShell
        return subprocess.run(command, shell=True, capture_output=True, text=True)
    return None

