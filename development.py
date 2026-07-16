
# This is a example ai generated file to prototype a autonomous agent for software engineering tasks.


import os
import requests
import json
import re
import subprocess
import threading
import urllib.request
import urllib.parse
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.theme import Theme
from rich.live import Live

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "bold yellow",
    "danger": "bold red",
    "success": "bold green",
    "ai": "bold magenta",
    "user": "bold cyan"
})

console = Console(theme=custom_theme)

API_LOCK = threading.Lock()
LAST_API_CALL = 0.0
COOLDOWN_SECONDS = 4.0

KEYS_FILE = Path.home() / ".ai_cli_keys.json"

def load_keys():
    keys = {"square": "", "groq": ""}
    if "SQUARECLOUD_API_KEY" in os.environ: keys["square"] = os.environ["SQUARECLOUD_API_KEY"]
    if "GROQ_API_KEY" in os.environ: keys["groq"] = os.environ["GROQ_API_KEY"]
    
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                saved = json.load(f)
                if not keys["square"]: keys["square"] = saved.get("square", "")
                if not keys["groq"]: keys["groq"] = saved.get("groq", "")
        except Exception: pass

    if not keys["square"]:
        console.print(Panel("[bold yellow]🔑 Configuração Inicial[/bold yellow]\nA chave da SquareCloud é necessária.", border_style="yellow"))
        keys["square"] = Prompt.ask("SQUARECLOUD_API_KEY").strip()
        keys["groq"] = Prompt.ask("GROQ_API_KEY (Opcional para Fallback)", default="").strip()
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f)
    return keys

SYSTEM_PROMPT = """Você é um Agente de Engenharia de Software Autônomo.
Sempre antes de agir, retorne um bloco <plan> com os passos do que você fará.

FORMATO:
<plan>
1. Passo 1
2. Passo 2
</plan>
```json
{"action": "nome", "parametro": "valor"}
```

FERRAMENTAS:
search_code, run_command, create_file, edit_file, read_file, list_directory, web_search."""

def execute_tool(action_data):
    action = action_data.get("action")
    try:
        if action == "run_command":
            cmd = action_data.get("command", "")
            console.print(f"\n[info]▶ Executando comando:[/info] [white]{cmd}[/white]")
            if Confirm.ask("[warning]Confirmar?[/warning]", default=True):
                if cmd.strip().startswith("cd "):
                    os.chdir(os.path.expanduser(cmd.strip()[3:].strip()))
                    return f"Diretório alterado para {os.getcwd()}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return (result.stdout + result.stderr).strip() or "Executado."
            return "Cancelado."
        elif action == "create_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            content = action_data.get("content", "")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return f"Criado: {path}"
        elif action == "edit_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            old, new = action_data.get("old_text", ""), action_data.get("new_text", "")
            with open(path, "r", encoding="utf-8") as f: content = f.read()
            if old in content:
                with open(path, "w", encoding="utf-8") as f: f.write(content.replace(old, new, 1))
                return f"Editado: {path}"
            return "Erro: texto não encontrado."
        elif action == "read_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            with open(path, "r", encoding="utf-8") as f: return f.read(10000)
        elif action == "list_directory":
            return "\n".join(os.listdir(os.path.expanduser(action_data.get("path", ".")))[:100])
        elif action == "search_code":
            query, p = action_data.get("query", ""), os.path.expanduser(action_data.get("path", "."))
            results = []
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__']]
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f):
                                if query in line: results.append(f"{filepath}:{i+1}: {line.strip()}")
                    except: pass
            return "\n".join(results[:50])
        elif action == "web_search":
            q = action_data.get("query", "")
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req).read().decode('utf-8')
            return "\n\n".join([re.sub(r'<[^>]+>', '', s).strip() for s in re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.S | re.I)[:4]])
    except Exception as e: return f"Erro: {str(e)}"
    return "Ação inválida."

def process_stream_response(resp):
    is_stream = "text/event-stream" in resp.headers.get("Content-Type", "")
    if is_stream:
        for line in resp.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: ") and line_str != "data: [DONE]":
                    try:
                        chunk = json.loads(line_str[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta and delta["content"]: yield delta["content"]
                    except: pass
    else:
        try:
            content = resp.json()["choices"][0]["message"]["content"]
            for word in content.split(" "): yield word + " "
        except: yield "Erro."

def stream_ai_api(messages, keys):
    global LAST_API_CALL
    with API_LOCK:
        elapsed = time.time() - LAST_API_CALL
        if elapsed < COOLDOWN_SECONDS: time.sleep(COOLDOWN_SECONDS - elapsed)
        LAST_API_CALL = time.time()
        try:
            resp = requests.post("https://api.squarecloud.app/v2/ai/chat/completions",
                headers={"Authorization": f"Bearer {keys['square']}"},
                json={"model": "cubic", "messages": messages}, stream=True, timeout=30)
            if resp.status_code == 200:
                yield from process_stream_response(resp)
                return
            yield f"Erro API: {resp.status_code}"
        except Exception as e: yield f"Erro: {e}"

class OllamaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        msgs = data.get('messages', [])
        full_res = "".join(list(stream_ai_api(msgs, load_keys())))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"message": {"content": full_res}}).encode())

def format_for_display(text):
    return re.sub(r'<think>(.*?)</think>', r'\n> 💭 \1\n', text, flags=re.S)

def main():
    keys = load_keys()
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 11434), OllamaHandler).serve_forever(), daemon=True).start()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    while True:
        try:
            inp = console.input(f"\n[user]❯ ({os.getcwd()})[/user] ").strip()
            if inp.lower() == "/clear":
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                continue
            if inp.lower() in ['exit', 'quit']: break
            if not inp: continue
            
            messages.append({"role": "user", "content": inp})
            
            full_message = ""
            iterator = stream_ai_api(messages, keys)
            with Live(Markdown(""), refresh_per_second=15, console=console) as live:
                for chunk in iterator:
                    full_message += chunk
                    live.update(Markdown(format_for_display(full_message)))
            
            messages.append({"role": "assistant", "content": full_message})

            plan_match = re.search(r'<plan>(.*?)</plan>', full_message, re.S)
            if plan_match:
                console.print(Panel(plan_match.group(1).strip(), title="🧠 Plano de Ação", border_style="blue"))

            blocks = re.findall(r'```(?:json)?\n?(.*?)\n?```', full_message, re.S)
            for b in blocks:
                try:
                    act = json.loads(b)
                    if "action" in act:
                        res = execute_tool(act)
                        console.print(f"[info]RESULTADO:[/info] {res}")
                        messages.append({"role": "user", "content": f"RESULTADO:\n{res}"})
                except: pass
                        
        except KeyboardInterrupt: break

if __name__ == "__main__":
    main()