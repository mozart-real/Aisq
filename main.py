# This file is not ai generated, only the main code to run the ai agent in terminal, and load the keys from environment or file.

# Helped by Visual Studio Code Inline Suggestions.

import os
import requests
import json
import re
import subprocess
import threading
import urllib.request
import urllib.parse
import time
import socket
import shutil
from datetime import datetime
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
COOLDOWN_SECONDS = 2.0

BASE_DIR = Path(os.getcwd())
KEYS_FILE = Path.home() / ".ai_cli_keys.json"
SKILLS_DIR = BASE_DIR / "skills"
HISTORY_DIR = Path.home() / ".aisq_history"
HISTORY_DIR.mkdir(exist_ok=True)

# Global variables
GLOBAL_KEYS = {}
ACTIVE_PROVIDER = "square"
ACTIVE_MODEL = "cubic"
SESSION_ENV = os.environ.copy()

class OllamaHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return
            
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if self.path == "/api/chat":
            messages = data.get("messages", [])
            stream = data.get("stream", True)
            
            if stream:
                for chunk in stream_ai_api(messages, GLOBAL_KEYS):
                    response_chunk = {
                        "model": data.get("model", ACTIVE_MODEL),
                        "created_at": datetime.now().isoformat(),
                        "message": {"role": "assistant", "content": chunk},
                        "done": False
                    }
                    self.wfile.write((json.dumps(response_chunk) + "\n").encode('utf-8'))
                    self.wfile.flush()
                done_chunk = {
                    "model": data.get("model", ACTIVE_MODEL),
                    "created_at": datetime.now().isoformat(),
                    "done": True
                }
                self.wfile.write((json.dumps(done_chunk) + "\n").encode('utf-8'))
                self.wfile.flush()
            else:
                full_content = "".join(list(stream_ai_api(messages, GLOBAL_KEYS)))
                response_full = {
                    "model": data.get("model", ACTIVE_MODEL),
                    "created_at": datetime.now().isoformat(),
                    "message": {"role": "assistant", "content": full_content},
                    "done": True
                }
                self.wfile.write(json.dumps(response_full).encode('utf-8'))
                self.wfile.flush()
                
        elif self.path == "/api/generate":
            prompt = data.get("prompt", "")
            stream = data.get("stream", True)
            messages = [{"role": "user", "content": prompt}]
            
            if stream:
                for chunk in stream_ai_api(messages, GLOBAL_KEYS):
                    response_chunk = {
                        "model": data.get("model", ACTIVE_MODEL),
                        "created_at": datetime.now().isoformat(),
                        "response": chunk,
                        "done": False
                    }
                    self.wfile.write((json.dumps(response_chunk) + "\n").encode('utf-8'))
                    self.wfile.flush()
                done_chunk = {
                    "model": data.get("model", ACTIVE_MODEL),
                    "created_at": datetime.now().isoformat(),
                    "done": True
                }
                self.wfile.write((json.dumps(done_chunk) + "\n").encode('utf-8'))
                self.wfile.flush()
            else:
                full_content = "".join(list(stream_ai_api(messages, GLOBAL_KEYS)))
                response_full = {
                    "model": data.get("model", ACTIVE_MODEL),
                    "created_at": datetime.now().isoformat(),
                    "response": full_content,
                    "done": True
                }
                self.wfile.write(json.dumps(response_full).encode('utf-8'))
                self.wfile.flush()
                
        elif self.path in ["/v1/chat/completions", "/v1/completions"]:
            messages = data.get("messages", [])
            stream = data.get("stream", True)
            
            if stream:
                for chunk in stream_ai_api(messages, GLOBAL_KEYS):
                    response_chunk = {
                        "id": "chatcmpl-cubic",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": ACTIVE_MODEL,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]
                    }
                    self.wfile.write(f"data: {json.dumps(response_chunk)}\n\n".encode('utf-8'))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                full_content = "".join(list(stream_ai_api(messages, GLOBAL_KEYS)))
                response_full = {
                    "id": "chatcmpl-cubic",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": ACTIVE_MODEL,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": full_content}, "finish_reason": "stop"}]
                }
                self.wfile.write(json.dumps(response_full).encode('utf-8'))
                self.wfile.flush()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def setup_windows_terminal():
    if os.name == 'nt':
        try:
            from ctypes import windll, wintypes
            kernel32 = windll.kernel32
            hStdOut = kernel32.GetStdHandle(-11)
            mode = wintypes.DWORD()
            kernel32.GetConsoleMode(hStdOut, wintypes.BYREF(mode))
            kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004)
        except Exception:
            pass

def select_default_provider(keys):
    global ACTIVE_PROVIDER, ACTIVE_MODEL
    for p in ["square", "gemini", "openai", "anthropic", "groq"]:
        if keys.get(p):
            ACTIVE_PROVIDER = p
            if p == "square": ACTIVE_MODEL = "cubic"
            elif p == "gemini": ACTIVE_MODEL = "gemini-2.5-flash"
            elif p == "openai": ACTIVE_MODEL = "gpt-4o-mini"
            elif p == "anthropic": ACTIVE_MODEL = "claude-3-5-sonnet-20241022"
            elif p == "groq": ACTIVE_MODEL = "llama-3.3-70b-versatile"
            break

def setup_providers_interactive(existing_keys=None):
    if existing_keys is None:
        existing_keys = {}
    console.print(Panel(
        "[bold yellow] Configuração de Provedores[/bold yellow]\n"
        "Insira as chaves de API correspondentes. Deixe em branco para ignorar ou manter a atual.",
        border_style="yellow"
    ))
    new_keys = {}
    new_keys["square"] = Prompt.ask("SQUARECLOUD_API_KEY", default=existing_keys.get("square", "")).strip()
    new_keys["gemini"] = Prompt.ask("GEMINI_API_KEY", default=existing_keys.get("gemini", "")).strip()
    new_keys["openai"] = Prompt.ask("OPENAI_API_KEY", default=existing_keys.get("openai", "")).strip()
    new_keys["anthropic"] = Prompt.ask("ANTHROPIC_API_KEY", default=existing_keys.get("anthropic", "")).strip()
    new_keys["groq"] = Prompt.ask("GROQ_API_KEY", default=existing_keys.get("groq", "")).strip()
    try:
        with open(KEYS_FILE, 'w') as f:
            json.dump(new_keys, f)
        console.print("[success]Configurações salvas em ~/.ai_cli_keys.json![/success]")
    except Exception as e:
        console.print(f"[danger]Erro ao salvar configurações: {e}[/danger]")
    select_default_provider(new_keys)
    return new_keys

def load_keys():
    keys = {
        "square": os.environ.get("SQUARECLOUD_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", ""),
        "gemini": os.environ.get("GEMINI_API_KEY", ""),
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", "")
    }
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                saved = json.load(f)
                for k in keys:
                    if not keys[k]: keys[k] = saved.get(k, "")
        except Exception: pass

    if not KEYS_FILE.exists() and not any(keys.values()):
        keys = setup_providers_interactive(keys)
    else:
        select_default_provider(keys)
    return keys

def load_skills(query=None):
    skills_text = ""
    if not SKILLS_DIR.exists():
        SKILLS_DIR.mkdir(exist_ok=True)
        example_skill = SKILLS_DIR / "example.md"
        if not example_skill.exists():
            with open(example_skill, "w", encoding="utf-8") as f:
                f.write("# Exemplo de Skill\nEsta é uma habilidade de exemplo que ensina o agente a ser mais educado.")
    
    files_to_load = list(SKILLS_DIR.glob("*.md"))
    if query:
        query_words = set(re.findall(r'\w+', query.lower()))
        matched_files = []
        for skill_file in files_to_load:
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                content_lower = content.lower()
                content_words = set(re.findall(r'\w+', content_lower))
                match_score = len(query_words.intersection(content_words))
                if skill_file.stem.lower() in query.lower():
                    match_score += 10
                if match_score > 0:
                    matched_files.append((match_score, skill_file, content))
            except Exception as e:
                console.print(f"[danger]Erro ao carregar skill {skill_file.name}: {e}[/danger]")
        
        matched_files.sort(key=lambda x: x[0], reverse=True)
        for score, file, content in matched_files[:3]:
            skills_text += f"\n\n--- SKILL: {file.stem} ---\n{content}\n"
    else:
        for skill_file in files_to_load:
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                skills_text += f"\n\n--- SKILL: {skill_file.stem} ---\n{content}\n"
            except Exception as e:
                console.print(f"[danger]Erro ao carregar skill {skill_file.name}: {e}[/danger]")
    return skills_text

SYSTEM_PROMPT_BASE = """Você é Cubic um agente de ia disponivel para varias tarefas mais principalmente envolvendo programação operando diretamente no terminal do usuário.
Sua prioridade é investigar, planejar e executar alterações em código e sistemas com máxima autonomia e precisão.

DIRETRIZES DE AÇÃO:
1. EXPLORE: Se não souber onde algo está, não adivinhe. Use 'summarize_directory' ou 'search_code'.
2. VERIFIQUE: Leia os arquivos ('read_file') ou obtenha info ('get_file_info') antes de modificar.
3. EXECUTE: Faça alterações com 'edit_file', 'create_file' ou rode comandos com 'run_command'.
4. Seja conciso e direto. Você não é um assistente de bate-papo, você é um agente de execução técnica.

FORMATO DE FERRAMENTA:
Você pode usar blocos JSON Markdown ou tags XML.
Exemplo JSON:
```json
{"action": "nome_da_ferramenta", "parametro": "valor"}
```

Exemplo XML (Preferencial):
<tool_call>
<function=nome_da_ferramenta>
<parameter=nome_do_parametro>valor</parameter>
</function>
</tool_call>

FERRAMENTAS DISPONÍVEIS:
- search_code: {"action": "search_code", "query": "texto", "path": ".", "extension": ".py"}
- run_command: {"action": "run_command", "command": "comando"}
- create_file: {"action": "create_file", "filepath": "caminho", "content": "texto"}
- edit_file: {"action": "edit_file", "filepath": "caminho", "old_text": "antigo", "new_text": "novo"}
- read_file: {"action": "read_file", "filepath": "caminho"}
- list_directory: {"action": "list_directory", "path": "caminho"}
- delete_file: {"action": "delete_file", "filepath": "caminho"}
- move_file: {"action": "move_file", "src": "origem", "dst": "destino"}
- copy_file: {"action": "copy_file", "src": "origem", "dst": "destino"}
- get_file_info: {"action": "get_file_info", "filepath": "caminho"}
- http_request: {"action": "http_request", "method": "GET/POST", "url": "url", "data": {}, "headers": {}}
- check_port: {"action": "check_port", "port": 8080}
- read_logs: {"action": "read_logs", "filepath": "caminho", "lines": 50}
- summarize_directory: {"action": "summarize_directory", "path": "."}
- get_time: {"action": "get_time"}
- web_search: {"action": "web_search", "query": "pesquisa"}

NÃO explique o que vai fazer antes. Apenas emita o bloco JSON ou XML para agir."""

AUTO_PROMPT = """Você está agora no MODO AUTOMAÇÃO.
Neste modo, você tem permissão para planejar e executar múltiplas etapas sem pedir confirmação constante.
Seu objetivo é resolver o problem complexo fornecido pelo usuário de ponta a ponta.

REGRAS ADICIONAIS DE AUTOMAÇÃO:
1. PENSE EM ETAPAS: Quebre a tarefa em sub-tarefas claras.
2. AUTO-CORREÇÃO: Se um comando ou ferramenta falhar, analise o erro, corrija a chamada e tente novamente.
3. RELATE O PROGRESSO: Após cada ferramenta executada, descreva brevemente o que foi feito e qual o próximo passo.
4. FINALIZAÇÃO: Quando terminar tudo, emita uma mensagem final clara resumindo o que foi realizado.

Você continuará executando ferramentas até que decida que o objetivo foi atingido ou que não há mais nada a ser feito."""

def get_full_system_prompt(query=None):
    skills = load_skills(query)
    prompt = SYSTEM_PROMPT_BASE
    if skills:
        prompt += "\n\nCONHECIMENTOS ADICIONAIS (SKILLS RELEVANTES):" + skills
    return prompt

def execute_tool(action_data, auto_mode=False):
    global SESSION_ENV
    action = action_data.get("action")
    try:
        if action == "run_command":
            cmd = action_data.get("command", "")
            console.print(f"\n[info]▶ Executando comando:[/info] [white]{cmd}[/white]")
            
            if not auto_mode:
                if not Confirm.ask("[warning]Confirmar?[/warning]", default=True):
                    return "Ação cancelada pelo usuário."
            
            marker = "---CUBIC_ENV_CWD_MARKER---"
            separator = ";" if os.name != 'nt' else "&"
            py_cmd = "python3" if shutil.which("python3") else "python"
            env_cmd = f"{py_cmd} -c \"import os, json; print(os.getcwd()); print(json.dumps(dict(os.environ)))\""
            
            full_cmd = f"({cmd}) {separator} echo {marker} {separator} {env_cmd}"
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, env=SESSION_ENV)
            stdout = result.stdout
            stderr = result.stderr
            
            if marker in stdout:
                parts = stdout.split(marker)
                command_output = parts[0].rstrip()
                meta_lines = parts[1].strip().splitlines()
                if len(meta_lines) >= 2:
                    new_cwd = meta_lines[0].strip()
                    env_json_str = meta_lines[1].strip()
                    try:
                        if os.path.exists(new_cwd):
                            os.chdir(new_cwd)
                        new_env = json.loads(env_json_str)
                        SESSION_ENV.update(new_env)
                    except Exception:
                        pass
                output = (command_output + "\n" + stderr).strip()
            else:
                output = (stdout + "\n" + stderr).strip()
            return output or "Executado com sucesso (sem saída)."
            
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
            try:
                with open(path, "r", encoding="utf-8") as f: content = f.read()
            except Exception as e:
                return f"Erro ao ler arquivo: {e}"
                
            if old in content:
                new_content = content.replace(old, new, 1)
                
                # Exibir Diff
                import difflib
                from rich.syntax import Syntax
                diff = list(difflib.unified_diff(
                    content.splitlines(),
                    new_content.splitlines(),
                    fromfile=os.path.basename(path) + " (original)",
                    tofile=os.path.basename(path) + " (modificado)",
                    lineterm=""
                ))
                if diff:
                    diff_text = "\n".join(diff)
                    console.print(Panel(Syntax(diff_text, "diff", theme="monokai"), title="Alterações propostas", border_style="cyan"))
                
                if not auto_mode:
                    if not Confirm.ask("[warning]Confirmar alteração?[/warning]", default=True):
                        return "Ação cancelada pelo usuário."
                        
                with open(path, "w", encoding="utf-8") as f: f.write(new_content)
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
 
        elif action == "delete_file":
            path = os.path.expanduser(action_data.get("filepath", ""))
            console.print(f"\n[danger]▶ Deletando arquivo:[/danger] [white]{path}[/white]")
            if not auto_mode:
                if not Confirm.ask("[warning]Tem certeza?[/warning]", default=False):
                    return "Operação cancelada."
            os.remove(path)
            return f"Arquivo {path} removido."
 
        elif action == "move_file":
            src, dst = os.path.expanduser(action_data.get("src", "")), os.path.expanduser(action_data.get("dst", ""))
            console.print(f"\n[info]▶ Movendo:[/info] [dim]{src} -> {dst}[/dim]")
            shutil.move(src, dst)
            return f"Movido com sucesso para {dst}"
 
        elif action == "copy_file":
            src, dst = os.path.expanduser(action_data.get("src", "")), os.path.expanduser(action_data.get("dst", ""))
            console.print(f"\n[info]▶ Copiando:[/info] [dim]{src} -> {dst}[/dim]")
            shutil.copy2(src, dst)
            return f"Copiado com sucesso para {dst}"
 
        elif action == "get_file_info":
            path = os.path.expanduser(action_data.get("filepath", ""))
            stats = os.stat(path)
            info = {
                "size_bytes": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                "is_file": os.path.isfile(path),
                "is_dir": os.path.is_dir(path)
            }
            return json.dumps(info, indent=2)
 
        elif action == "http_request":
            method = action_data.get("method", "GET").upper()
            url = action_data.get("url", "")
            data = action_data.get("data", None)
            headers = action_data.get("headers", {})
            console.print(f"\n[info]▶ HTTP {method}:[/info] [dim]{url}[/dim]")
            r = requests.request(method, url, json=data, headers=headers, timeout=15)
            return f"Status: {r.status_code}\nBody: {r.text[:5000]}"
 
        elif action == "check_port":
            port = int(action_data.get("port", 0))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                is_open = s.connect_ex(('127.0.0.1', port)) == 0
            return f"Porta {port} está {'EM USO' if is_open else 'LIVRE'}."
 
        elif action == "read_logs":
            path = os.path.expanduser(action_data.get("filepath", ""))
            lines_count = int(action_data.get("lines", 50))
            console.print(f"\n[info]▶ Lendo logs ({lines_count} linhas):[/info] [dim]{path}[/dim]")
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[-lines_count:])
 
        elif action == "summarize_directory":
            path = os.path.expanduser(action_data.get("path", "."))
            output = []
            for root, dirs, files in os.walk(path):
                level = root.replace(path, '').count(os.sep)
                indent = ' ' * 4 * level
                output.append(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files[:10]:
                    output.append(f"{subindent}{f}")
                if len(files) > 10: output.append(f"{subindent}... ({len(files)-10} mais arquivos)")
                if level > 2: break
            return "\n".join(output)
 
        elif action == "get_time":
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 
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

def process_stream_response(resp, provider="openai"):
    is_stream = "text/event-stream" in resp.headers.get("Content-Type", "")
    if is_stream:
        for line in resp.iter_lines():
            if line:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith("data: "):
                    data_content = line_str[6:].strip()
                    if data_content == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_content)
                        if provider == "anthropic":
                            if chunk.get("type") == "content_block_delta":
                                text = chunk.get("delta", {}).get("text", "")
                                if text: yield text
                        else:
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                    except json.JSONDecodeError: pass
    else:
        try:
            res_json = resp.json()
            if provider == "anthropic":
                content = res_json.get("content", [{}])[0].get("text", "")
            else:
                content = res_json["choices"][0]["message"]["content"]
            words = content.split(" ")
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                time.sleep(0.01)
        except Exception as e:
            yield f"Erro ao processar resposta: {e}"

def stream_ai_api(messages, keys):
    global LAST_API_CALL, ACTIVE_PROVIDER, ACTIVE_MODEL
    
    providers_to_try = [ACTIVE_PROVIDER]
    for p in ["square", "gemini", "openai", "anthropic", "groq"]:
        if p != ACTIVE_PROVIDER and keys.get(p):
            providers_to_try.append(p)
            
    for prov in providers_to_try:
        model = ACTIVE_MODEL
        if prov != ACTIVE_PROVIDER:
            defaults = {
                "square": "cubic",
                "gemini": "gemini-2.5-flash",
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-sonnet-20241022",
                "groq": "llama-3.3-70b-versatile"
            }
            model = defaults[prov]
            yield f"\n[warning] Redirecionando para {prov} ({model}) devido a erro ou timeout...[/warning]\n"
            
        with API_LOCK:
            elapsed = time.time() - LAST_API_CALL
            if elapsed < COOLDOWN_SECONDS: time.sleep(COOLDOWN_SECONDS - elapsed)
            LAST_API_CALL = time.time()
            
            try:
                if prov == "square":
                    url = "https://api.squarecloud.app/v2/ai/chat/completions"
                    headers = {"Authorization": f"Bearer {keys['square']}"}
                    json_data = {"model": model, "messages": messages}
                elif prov == "groq":
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {keys['groq']}"}
                    json_data = {"model": model, "messages": messages, "stream": True}
                elif prov == "gemini":
                    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                    headers = {"Authorization": f"Bearer {keys['gemini']}"}
                    json_data = {"model": model, "messages": messages, "stream": True}
                elif prov == "openai":
                    url = "https://api.openai.com/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {keys['openai']}"}
                    json_data = {"model": model, "messages": messages, "stream": True}
                elif prov == "anthropic":
                    url = "https://api.anthropic.com/v1/messages"
                    headers = {
                        "x-api-key": keys['anthropic'],
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                    system_msg = ""
                    filtered_msgs = []
                    for m in messages:
                        if m["role"] == "system":
                            system_msg += m["content"] + "\n"
                        else:
                            filtered_msgs.append(m)
                    json_data = {
                        "model": model,
                        "system": system_msg.strip(),
                        "messages": filtered_msgs,
                        "max_tokens": 4096,
                        "stream": True
                    }
                
                resp = requests.post(url, headers=headers, json=json_data, stream=True, timeout=30)
                if resp.status_code == 200:
                    yield from process_stream_response(resp, provider=prov)
                    return
            except Exception:
                continue
    yield "\n[danger]Erro: Todos os provedores de API falharam ou estão indisponíveis.[/danger]"

def extract_tool_calls(text):
    blocks = []
    json_raw_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.S)
    for raw in json_raw_blocks:
        clean_raw = re.sub(r'//.*', '', raw) 
        blocks.append(clean_raw)
    
    xml_tool_calls = re.findall(r'<tool_call>(.*?)</tool_call>', text, re.S | re.I)
    for xml_content in xml_tool_calls:
        func_match = re.search(r'<(?:function|action)=(.*?)>(.*?)(?:</(?:function|action)>|$)', xml_content, re.S | re.I)
        if func_match:
            func_name = func_match.group(1).strip()
            func_body = func_match.group(2).strip()
            d = {"action": func_name}
            params = re.findall(r'<(?:parameter|param)=(.*?)>(.*?)(?:</(?:parameter|param)>|$)', func_body, re.S | re.I)
            for k, v in params:
                d[k.strip()] = v.strip()
            if not params:
                json_match = re.search(r'(\{.*?\})', func_body, re.S)
                if json_match:
                    try:
                        inner_json = json.loads(json_match.group(1))
                        d.update(inner_json)
                    except: pass
            blocks.append(json.dumps(d))
        else:
            json_match = re.search(r'(\{.*?\})', xml_content, re.S)
            if json_match:
                blocks.append(json_match.group(1))

    xml_direct = re.findall(r'<(?:function|action)=(.*?)>(.*?)(?:</(?:function|action)>|$)', text, re.S | re.I)
    for name, cont in xml_direct:
        if any(name.strip() in b for b in blocks): continue
        d = {"action": name.strip()}
        for k, v in re.findall(r'<(?:parameter|param)=(.*?)>(.*?)(?:</(?:parameter|param)>|$)', cont, re.S | re.I):
            d[k.strip()] = v.strip()
        blocks.append(json.dumps(d))
    return blocks

def format_for_display(text):
    return re.sub(r'<think>(.*?)</think>', r'\n>  \1\n', text, flags=re.S)

def save_session(name, messages):
    try:
        with open(HISTORY_DIR / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[danger]Erro ao salvar sessão: {e}[/danger]")
        return False

def load_session(name):
    path = HISTORY_DIR / f"{name}.json"
    if not path.exists(): return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[danger]Erro ao carregar sessão: {e}[/danger]")
        return None

def list_history():
    files = list(HISTORY_DIR.glob("*.json"))
    if not files:
        console.print("[warning]Nenhuma sessão salva encontrada.[/warning]")
        return
    console.print("[info]Sessões disponíveis (restaurar com '/load <nome>'):[/info]")
    for file in files:
        mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        console.print(f"- [cyan]{file.stem}[/cyan] ({mtime})")

def show_help():
    help_text = """
### Comandos Disponíveis na CLI

| Comando | Descrição |
| :--- | :--- |
| `/help` | Exibe este menu de ajuda. |
| `/clear` | Limpa o contexto da conversa na memória e recarrega as Skills locais. |
| `/skills` | Lista todas as habilidades (.md) carregadas do diretório `./skills/`. |
| `/provider <nome>` | Altera o provedor de IA atual (`square`, `groq`, `gemini`, `openai`, `anthropic`). |
| `/config` | Abre o menu de configuração interativa de chaves de API. |
| `/history` | Lista as conversas salvas no diretório `~/.aisq_history/`. |
| `/save <nome>` | Salva o histórico da sessão de chat atual. |
| `/load <nome>` | Restaura uma sessão de chat anteriormente salva. |
| `/auto <prompt>` | Entra no modo de automação para executar tarefas complexas passo a passo. |
| `exit` / `quit` | Encerra a execução da CLI. |
"""
    console.print(Panel(Markdown(help_text), title="[bold magenta]Cubic Help Menu[/bold magenta]", border_style="magenta"))

def run_auto_mode(initial_prompt, keys):
    console.print(Panel("[bold green]ENTRANDO NO MODO AUTOMAÇÃO[/bold green]\nO Cubic agirá de forma autônoma.", border_style="green"))
    
    messages = [
        {"role": "system", "content": get_full_system_prompt(initial_prompt) + "\n\n" + AUTO_PROMPT},
        {"role": "user", "content": initial_prompt}
    ]
    
    step = 1
    while step <= 15:
        console.print(f"\n[info]⚙ Passo de Automação {step}...[/info]")
        full_message = ""
        iterator = stream_ai_api(messages, keys)
        with Live(Markdown(""), refresh_per_second=15, console=console) as live:
            for chunk in iterator:
                full_message += chunk
                live.update(Markdown(format_for_display(full_message)))
        
        if not full_message.strip(): break
        messages.append({"role": "assistant", "content": full_message})
        blocks = extract_tool_calls(full_message)
        if not blocks:
            console.print("\n[success]✔ Automação concluída.[/success]")
            break
        for b in blocks:
            try:
                try:
                    act = json.loads(b)
                except json.JSONDecodeError as je:
                    raise ValueError(f"Formato JSON inválido: {je}. Certifique-se de que todas as aspas estão corretas, não há vírgulas sobrando e o JSON está completo.")
                
                if "action" in act:
                    res = execute_tool(act, auto_mode=True)
                    messages.append({"role": "user", "content": f"RESULTADO DA FERRAMENTA:\n{res}"})
                else:
                    raise ValueError("O JSON fornecido não contém o campo obrigatório 'action'.")
            except Exception as e:
                err_msg = f"ERRO NA CHAMADA DA FERRAMENTA: {e}\nPor favor, corrija a chamada e envie-a novamente no formato correto (JSON ou XML)."
                messages.append({"role": "user", "content": err_msg})
        step += 1

def main():
    if os.name == 'nt':
        setup_windows_terminal()
        
    global GLOBAL_KEYS, ACTIVE_PROVIDER, ACTIVE_MODEL
    GLOBAL_KEYS = load_keys()
    
    # Start Ollama proxy thread
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 11434), OllamaHandler).serve_forever(), daemon=True).start()
    
    welcome_msg = (
        "[bold magenta]Cubic CLI alpha/2.5[/bold magenta]\n"
        "[dim]Sistema de Skills Ativado! Adicione arquivos .md em ./skills/[/dim]\n"
        f"[info]Provedor Ativo: {ACTIVE_PROVIDER} ({ACTIVE_MODEL})[/info]\n"
        "Digite [cyan]/help[/cyan] para ver a lista de comandos."
    )
    autosave_file = HISTORY_DIR / "autosave_current.json"
    if autosave_file.exists():
        welcome_msg += "\n[dim]Sessão anterior encontrada. Digite [cyan]/load autosave_current[/cyan] para restaurar.[/dim]"
    
    console.print(Panel(welcome_msg, border_style="magenta"))
    
    messages = [{"role": "system", "content": get_full_system_prompt()}]
    
    while True:
        try:
            inp = console.input(f"\n[user]❯ ({os.getcwd()})[/user] ").strip()
            
            if inp.lower() == "/help":
                show_help()
                continue
                
            if inp.lower() == "/clear":
                messages = [{"role": "system", "content": get_full_system_prompt()}]
                console.print("[success] Memória limpa e Skills recarregadas![/success]")
                continue
            
            if inp.lower() == "/skills":
                skills = load_skills()
                if skills:
                    console.print(Panel(Markdown(skills), title="Skills Carregadas", border_style="cyan"))
                else:
                    console.print("[warning]Nenhuma skill encontrada em ./skills/[/warning]")
                continue

            if inp.lower() == "/config":
                GLOBAL_KEYS.update(setup_providers_interactive(GLOBAL_KEYS))
                messages[0] = {"role": "system", "content": get_full_system_prompt()}
                continue

            if inp.lower().startswith("/save "):
                name = inp[6:].strip()
                if name:
                    if save_session(name, messages):
                        console.print(f"[success]Sessão '{name}' salva com sucesso![/success]")
                else:
                    console.print("[warning]Uso: /save <nome_da_sessao>[/warning]")
                continue
            
            if inp.lower().startswith("/load "):
                name = inp[6:].strip()
                if name:
                    loaded = load_session(name)
                    if loaded is not None:
                        messages = loaded
                        console.print(f"[success]Sessão '{name}' carregada! ({len(messages)} mensagens no contexto)[/success]")
                    else:
                        console.print(f"[danger]Sessão '{name}' não encontrada.[/danger]")
                else:
                    console.print("[warning]Uso: /load <nome_da_sessao>[/warning]")
                continue
            
            if inp.lower() == "/history":
                list_history()
                continue
                
            if inp.lower().startswith("/provider "):
                parts = inp.split()
                prov = parts[1].lower() if len(parts) > 1 else ""
                prov_models = {
                    "square": ("square", "cubic"),
                    "groq": ("groq", "llama-3.3-70b-versatile"),
                    "gemini": ("gemini", "gemini-2.5-flash"),
                    "openai": ("openai", "gpt-4o-mini"),
                    "anthropic": ("anthropic", "claude-3-5-sonnet-20241022")
                }
                if prov in prov_models:
                    p_name, m_name = prov_models[prov]
                    if GLOBAL_KEYS.get(p_name):
                        ACTIVE_PROVIDER = p_name
                        ACTIVE_MODEL = m_name
                        messages[0] = {"role": "system", "content": get_full_system_prompt()}
                        console.print(f"[success]Provedor alterado para '{p_name}' (modelo: '{m_name}')![/success]")
                    else:
                        console.print(f"[danger]Erro: Chave para o provedor '{p_name}' não configurada.[/danger]")
                else:
                    console.print("[warning]Provedores disponíveis: square, groq, gemini, openai, anthropic[/warning]")
                continue

            if inp.lower().startswith("/auto"):
                prompt = inp[5:].strip() or Prompt.ask("[bold green]O que devo automatizar?[/bold green]")
                run_auto_mode(prompt, GLOBAL_KEYS)
                continue

            if inp.lower() in ['exit', 'quit', 'sair']: break
            if not inp: continue
            
            messages[0] = {"role": "system", "content": get_full_system_prompt(inp)}
            messages.append({"role": "user", "content": inp})
            
            while True:
                full_message = ""
                console.print("")
                iterator = stream_ai_api(messages, GLOBAL_KEYS)
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
                save_session("autosave_current", messages)
                
                blocks = extract_tool_calls(full_message)
                if not blocks: break
                
                for b in blocks:
                    try:
                        try:
                            act = json.loads(b)
                        except json.JSONDecodeError as je:
                            raise ValueError(f"Formato JSON inválido: {je}. Certifique-se de que todas as aspas estão corretas, não há vírgulas sobrando e o JSON está completo.")
                        
                        if "action" in act:
                            res = execute_tool(act)
                            messages.append({"role": "user", "content": f"RESULTADO:\n{res}"})
                        else:
                            raise ValueError("O JSON fornecido não contém o campo obrigatório 'action'.")
                    except Exception as e:
                        err_msg = f"ERRO NA CHAMADA DA FERRAMENTA: {e}\nPor favor, corrija a chamada e envie-a novamente no formato correto."
                        messages.append({"role": "user", "content": err_msg})
            
        except (KeyboardInterrupt, EOFError): break
        except Exception as e: console.print(f"\n[danger]Erro crítico: {e}[/danger]")

if __name__ == "__main__":
    main()
