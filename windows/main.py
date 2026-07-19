# This file is not ai generated, only the main code to run the ai agent in terminal, and load the keys from environment or file.

# Helped by Visual Studio Code Inline Suggestions.

import os
import requests
import win_compat 
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
COOLDOWN_SECONDS = 4.0

BASE_DIR = Path(os.getcwd())
KEYS_FILE = Path.home() / ".ai_cli_keys.json"
SKILLS_DIR = BASE_DIR / "skills"

class OllamaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "model": data.get("model", "llama3"),
            "created_at": datetime.now().isoformat(),
            "response": "Ollama compatibility layer active.",
            "done": True
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        return

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
        console.print(Panel("[bold yellow] Configuração Inicial[/bold yellow]\nA chave da SquareCloud é necessária.", border_style="yellow"))
        keys["square"] = Prompt.ask("SQUARECLOUD_API_KEY").strip()
        keys["groq"] = Prompt.ask("GROQ_API_KEY (Opcional para Fallback mas altamente recomendado)", default="").strip()
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f)
    return keys

def load_skills():
    skills_text = ""
    if not SKILLS_DIR.exists():
        SKILLS_DIR.mkdir(exist_ok=True)
        # Criar uma skill de exemplo se não existir nenhuma
        example_skill = SKILLS_DIR / "example.md"
        if not example_skill.exists():
            with open(example_skill, "w", encoding="utf-8") as f:
                f.write("# Exemplo de Skill\nEsta é uma habilidade de exemplo que ensina o agente a ser mais educado.")
    
    for skill_file in SKILLS_DIR.glob("*.md"):
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
Seu objetivo é resolver o problema complexo fornecido pelo usuário de ponta a ponta.

REGRAS ADICIONAIS DE AUTOMAÇÃO:
1. PENSE EM ETAPAS: Quebre a tarefa em sub-tarefas claras.
2. AUTO-CORREÇÃO: Se um comando falhar, analise o erro e tente uma abordagem diferente.
3. RELATE O PROGRESSO: Após cada ferramenta executada, descreva brevemente o que foi feito e qual o próximo passo.
4. FINALIZAÇÃO: Quando terminar tudo, emita uma mensagem final clara resumindo o que foi realizado.

Você continuará executando ferramentas até que decida que o objetivo foi atingido ou que não há mais nada a ser feito."""

def get_full_system_prompt():
    skills = load_skills()
    prompt = SYSTEM_PROMPT_BASE
    if skills:
        prompt += "\n\nCONHECIMENTOS ADICIONAIS (SKILLS):" + skills
    return prompt

def execute_tool(action_data, auto_mode=False):
    action = action_data.get("action")
    try:
        if action == "run_command":
            cmd = action_data.get("command", "")
            console.print(f"\n[info]▶ Executando comando:[/info] [white]{cmd}[/white]")
            
            if not auto_mode:
                if not Confirm.ask("[warning]Confirmar?[/warning]", default=True):
                    return "Ação cancelada pelo usuário."
            
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
                if level > 2: break # Limita profundidade
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
    use_groq = False
    
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
            
            if resp.status_code != 200:
                use_groq = True
                
        except (requests.exceptions.RequestException, socket.timeout):
            use_groq = True

    if use_groq and keys.get("groq"):
        yield "\n[warning] Redirecionando para Groq (Llama 3.3) devido a erro ou timeout na SquareCloud...[/warning]\n"
        try:
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {keys['groq']}"},
                json={"model": "llama-3.3-70b-versatile", "messages": messages, "stream": True},
                stream=True, timeout=30)
            if resp.status_code == 200:
                yield from process_stream_response(resp)
                return
            yield f"\n[danger]Erro na API Groq: Código {resp.status_code}[/danger]"
        except Exception as e:
            yield f"\n[danger]Erro crítico no Fallback: {e}[/danger]"
    else:
        yield "\n[danger]Erro: API da SquareCloud indisponível e Groq não configurado.[/danger]"

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

def run_auto_mode(initial_prompt, keys):
    console.print(Panel("[bold green]ENTRANDO NO MODO AUTOMAÇÃO[/bold green]\nO Cubic agirá de forma autônoma.", border_style="green"))
    
    messages = [
        {"role": "system", "content": get_full_system_prompt() + "\n\n" + AUTO_PROMPT},
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
                act = json.loads(b)
                if "action" in act:
                    res = execute_tool(act, auto_mode=True)
                    messages.append({"role": "user", "content": f"RESULTADO DA FERRAMENTA:\n{res}"})
                else:
                    messages.append({"role": "user", "content": "Erro: JSON sem chave 'action'."})
            except Exception as e:
                messages.append({"role": "user", "content": f"Erro ao processar ferramenta: {e}"})
        step += 1

def main():
    # Setup inicial para Windows
    if os.name == 'nt':
        win_compat.setup_windows_terminal()
        
    keys = load_keys()
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 11434), OllamaHandler).serve_forever(), daemon=True).start()
    
    current_prompt = get_full_system_prompt()
    messages = [{"role": "system", "content": current_prompt}]
    
    console.print(Panel("[bold magenta]Cubic CLI alpha/2.4[/bold magenta]\n[dim]Sistema de Skills Ativado! Adicione arquivos .md em ./skills/[/dim]", border_style="magenta"))
    
    while True:
        try:
            inp = console.input(f"\n[user]❯ ({os.getcwd()})[/user] ").strip()
            
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

            if inp.lower().startswith("/auto"):
                prompt = inp[5:].strip() or Prompt.ask("[bold green]O que devo automatizar?[/bold green]")
                run_auto_mode(prompt, keys)
                continue

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
                blocks = extract_tool_calls(full_message)
                if not blocks: break
                
                for b in blocks:
                    try:
                        act = json.loads(b)
                        if "action" in act:
                            res = execute_tool(act)
                            messages.append({"role": "user", "content": f"RESULTADO:\n{res}"})
                        else:
                            messages.append({"role": "user", "content": "Erro: JSON sem 'action'."})
                    except Exception as e:
                        messages.append({"role": "user", "content": f"Erro: {e}"})
            
        except KeyboardInterrupt: break
        except Exception as e: console.print(f"\n[danger]Erro crítico: {e}[/danger]")

if __name__ == "__main__":
    main()
