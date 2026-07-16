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

SYSTEM_PROMPT = """Você é um Agente de Engenharia de Software Autônomo de Elite operando diretamente no terminal do usuário.
Sua prioridade é investigar, planejar e executar alterações em código e sistemas com máxima autonomia e precisão.

DIRETRIZES DE AÇÃO:
1. EXPLORE: Se não souber onde algo está, não adivinhe. Use 'list_directory' ou a nova ferramenta 'search_code' para vasculhar o projeto.
2. VERIFIQUE: Leia os arquivos ('read_file') antes de tentar modificá-los ou rodar comandos neles.
3. EXECUTE: Faça alterações com 'edit_file' ou rode scripts com 'run_command'.
4. Seja conciso e direto. Você não é um assistente de bate-papo, você é um agente de execução técnica.

FORMATO DE FERRAMENTA:
Retorne APENAS blocos JSON Markdown para ações. É obrigatório ter a chave "action":
```json
{"action": "nome_da_ferramenta", "parametro": "valor"}
```

FERRAMENTAS DISPONÍVEIS:
- search_code: {"action": "search_code", "query": "def minhalogica", "path": ".", "extension": ".py"} (Busca um texto em todos os arquivos daquele tipo na pasta)
- run_command: {"action": "run_command", "command": "seu comando bash aqui"}
- create_file: {"action": "create_file", "filepath": "caminho", "content": "texto"}
- edit_file: {"action": "edit_file", "filepath": "caminho", "old_text": "texto_antigo_exato", "new_text": "texto_novo"}
- read_file: {"action": "read_file", "filepath": "caminho"}
- list_directory: {"action": "list_directory", "path": "caminho"}
- web_search: {"action": "web_search", "query": "pesquisa"}

NÃO explique o que vai fazer antes. Apenas emita o bloco JSON para agir."""

def execute_tool(action_data):
    action = action_data.get("action")
    try:
        if action == "run_command":
            cmd = action_data.get("command", "")
            console.print(f"\n[info]▶ Executando comando:[/info] [white]{cmd}[/white]")
            if Confirm.ask("[warning]Confirmar?[/warning]", default=True):
                if cmd.strip().startswith("cd "):
                    new_dir = cmd.strip()[3:].strip()
                    try:
                        os.chdir(os.path.expanduser(new_dir))
                        return f"Diretório alterado. Pasta atual: {os.getcwd()}"
                    except Exception as e:
                        return f"Erro ao mudar de diretório: {e}"
                else:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    return (result.stdout + result.stderr).strip() or "Executado com sucesso (sem saída)."
            return "Ação cancelada pelo usuário."
            
        elif action == "create_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            content = action_data.get("content", "")
            console.print(f"\n[info]▶ Criando arquivo:[/info] [cyan]{path}[/cyan]")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return f"Criado: {path}"
            
        elif action == "edit_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            old, new = action_data.get("old_text", ""), action_data.get("new_text", "")
            console.print(f"\n[info]▶ Editando arquivo:[/info] [cyan]{path}[/cyan]")
            with open(path, "r", encoding="utf-8") as f: content = f.read()
            if old in content:
                with open(path, "w", encoding="utf-8") as f: f.write(content.replace(old, new, 1))
                return f"Arquivo {path} editado com sucesso."
            return "Erro: texto original ('old_text') não encontrado no arquivo."
            
        elif action == "read_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            console.print(f"\n[info]▶ Lendo arquivo:[/info] [dim]{path}[/dim]")
            with open(path, "r", encoding="utf-8") as f: return f.read(10000)
            
        elif action == "list_directory":
            p = os.path.expanduser(action_data.get("path", "."))
            console.print(f"\n[info]▶ Listando diretório:[/info] [dim]{p}[/dim]")
            return "\n".join(os.listdir(p)[:100])

        elif action == "search_code":
            query = action_data.get("query", "")
            p = os.path.expanduser(action_data.get("path", "."))
            ext = action_data.get("extension", "")
            console.print(f"\n[info]▶ Buscando por '{query}' em '{p}'[/info]")
            results = []
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__']]
                for file in files:
                    if not ext or file.endswith(ext):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                for i, line in enumerate(f):
                                    if query in line:
                                        results.append(f"{filepath}:{i+1}: {line.strip()}")
                        except Exception: pass
            res_str = "\n".join(results[:50])
            if len(results) > 50: res_str += f"\n... (+{len(results)-50} resultados omitidos)"
            return res_str or "Nenhum resultado encontrado."
            
        elif action == "web_search":
            q = action_data.get("query", "")
            console.print(f"\n[info]▶ Pesquisando na web:[/info] [dim]{q}[/dim]")
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req).read().decode('utf-8')
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.S | re.I)
            return "\n\n".join([re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:4]])
            
    except Exception as e: return f"Erro na execução da ferramenta: {str(e)}"
    return "Ação inválida ou não reconhecida."

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
                    except json.JSONDecodeError: pass
    else:
        try:
            content = resp.json()["choices"][0]["message"]["content"]
            words = content.split(" ")
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                time.sleep(0.02)
        except Exception: yield "Erro ao processar resposta."

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
            if resp.status_code == 429 and keys.get("groq"):
                yield "\n[warning]⚡ Redirecionando para Groq (Llama 3.3)...[/warning]\n"
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {keys['groq']}"},
                    json={"model": "llama-3.3-70b-versatile", "messages": messages, "stream": True},
                    stream=True, timeout=30)
                if resp.status_code == 200: yield from process_stream_response(resp)
                return
            yield f"\n[danger]Erro na API: Código {resp.status_code}[/danger]"
        except requests.exceptions.RequestException as e: yield f"\n[danger]Erro de conexão: {e}[/danger]"

class OllamaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path in ['/api/chat', '/api/generate']:
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            msgs = data.get('messages', [{"role": "user", "content": data.get('prompt', '')}])
            res_chunks = list(stream_ai_api(msgs, load_keys()))
            full_res = "".join(res_chunks)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            out = {"model": "square-ai", "message": {"role": "assistant", "content": full_res or "Erro."}, "done": True}
            if self.path == '/api/generate': out["response"] = out["message"]["content"]
            self.wfile.write(json.dumps(out).encode())

def format_for_display(text):
    return re.sub(r'<think>(.*?)</think>', r'\n> 💭 \1\n', text, flags=re.S)

def main():
    keys = load_keys()
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 11434), OllamaHandler).serve_forever(), daemon=True).start()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    console.print(Panel("[bold magenta]🚀 AI CLI Agent v4.0[/bold magenta]\n[dim]Habilidades Autônomas + Streaming Ativados[/dim]", border_style="magenta"))
    
    while True:
        try:
            inp = console.input(f"\n[user]❯ ({os.getcwd()})[/user] ").strip()
            
            # --- COMANDO CLEAR ---
            if inp.lower() == "/clear":
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                console.print("[success]🚀 Memória limpa com sucesso! O agente foi resetado.[/success]")
                continue
            # ---------------------
            
            if inp.lower() in ['exit', 'quit', 'sair']: break
            if not inp: continue
            
            messages.append({"role": "user", "content": inp})
            
            while True:
                full_message = ""
                console.print("")
                iterator = stream_ai_api(messages, keys)
                with console.status("[dim]Processando...[/dim]", spinner="bouncingBar"):
                    try:
                        first_chunk = next(iterator)
                        full_message += first_chunk
                    except StopIteration: pass
                
                if full_message:
                    with Live(Markdown(format_for_display(full_message)), refresh_per_second=15, console=console) as live:
                        for chunk in iterator:
                            full_message += chunk
                            live.update(Markdown(format_for_display(full_message)))
                
                if not full_message.strip():
                    messages.pop()
                    break

                messages.append({"role": "assistant", "content": full_message})

                blocks = re.findall(r'```(?:json)?\n?(.*?)\n?```', full_message, re.S)
                xmls = re.findall(r'<(?:tool_call|function)=(.*?)>(.*?)(?:</(?:tool_call|function)>|$)', full_message, re.S | re.I)
                for name, cont in xmls:
                    d = {"action": name.strip()}
                    for k, v in re.findall(r'<(?:parameter|param)=(.*?)>(.*?)(?:</(?:parameter|param)>|$)', cont, re.S | re.I):
                        d[k.strip()] = v.strip()
                    blocks.append(json.dumps(d))

                if not blocks: break
                
                for b in blocks:
                    try:
                        act = json.loads(b)
                        if "action" in act:
                            res = execute_tool(act)
                            messages.append({"role": "user", "content": f"RESULTADO:\n{res}"})
                        else:
                            console.print("\n[danger]A IA retornou um JSON sem a chave 'action'.[/danger]")
                            messages.append({"role": "user", "content": "Erro: Seu JSON deve conter a chave 'action'."})
                    except json.JSONDecodeError as e:
                        console.print(f"\n[danger]Erro no JSON: {e}[/danger]")
                        messages.append({"role": "user", "content": "Erro de JSON: Retorne um JSON válido e sem aspas soltas."})
                        
        except KeyboardInterrupt: break
        except Exception as e: console.print(f"\n[danger]Erro Crítico no loop: {e}[/danger]")

if __name__ == "__main__":
    main()