#!/usr/bin/env python3
"""
URL Monitor - Monitora o status de URLs e exibe em um dashboard web.
"""

import requests
import threading
import time
import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Armazenamento de status das URLs
url_status = {}
lock = threading.Lock()

CONFIG_FILE = "urls_config.json"

def load_config():
    """Carrega as URLs do arquivo de configuração."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_config(urls):
    """Salva as URLs no arquivo de configuração."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(urls, f, indent=2)

def check_url(url_info):
    """Verifica o status de uma URL."""
    url = url_info['url']
    name = url_info.get('name', url)
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=10, verify=True)
        response_time = (time.time() - start_time) * 1000  # em ms
        
        status_code = response.status_code
        is_up = 200 <= status_code < 400
        
        with lock:
            url_status[url] = {
                'name': name,
                'url': url,
                'status_code': status_code,
                'is_up': is_up,
                'response_time': round(response_time, 2),
                'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': None
            }
            
    except Exception as e:
        with lock:
            url_status[url] = {
                'name': name,
                'url': url,
                'status_code': None,
                'is_up': False,
                'response_time': None,
                'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }

def monitor_urls(interval=30):
    """Monitora todas as URLs em loop."""
    while True:
        urls = load_config()
        for url_info in urls:
            check_url(url_info)
        
        # Se houver URLs para monitorar, faz o sleep
        if urls:
            time.sleep(interval)

@app.route('/')
def index():
    """Página principal com o dashboard."""
    urls = load_config()
    return render_template('index.html', urls=urls)

@app.route('/api/status')
def api_status():
    """Retorna o status de todas as URLs em JSON."""
    with lock:
        return jsonify(list(url_status.values()))

@app.route('/api/add', methods=['POST'])
def api_add_url():
    """Adiciona uma nova URL para monitorar."""
    data = request.json
    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    
    if not url:
        return jsonify({'error': 'URL é obrigatória'}), 400
    
    # Adiciona https se não tiver protocolo
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    urls = load_config()
    
    # Verifica se já existe
    for existing in urls:
        if existing['url'] == url:
            return jsonify({'error': 'URL já está sendo monitorada'}), 400
    
    urls.append({'url': url, 'name': name})
    save_config(urls)
    
    # Verifica imediatamente
    check_url({'url': url, 'name': name})
    
    return jsonify({'success': True})

@app.route('/api/remove/<url>', methods=['DELETE'])
def api_remove_url(url):
    """Remove uma URL do monitoramento."""
    urls = load_config()
    urls = [u for u in urls if u['url'] != url]
    save_config(urls)
    
    with lock:
        if url in url_status:
            del url_status[url]
    
    return jsonify({'success': True})

if __name__ == '__main__':
    # Carrega URLs iniciais se não houver configuração
    if not os.path.exists(CONFIG_FILE):
        default_urls = [
            {'url': 'https://www.google.com', 'name': 'Google'},
            {'url': 'https://www.github.com', 'name': 'GitHub'},
            {'url': 'https://squarecloud.app', 'name': 'Square Cloud'}
        ]
        save_config(default_urls)
    
    # Inicia o monitor em background
    monitor_thread = threading.Thread(target=monitor_urls, args=(30,), daemon=True)
    monitor_thread.start()
    
    # Verifica URLs iniciais
    urls = load_config()
    for url_info in urls:
        check_url(url_info)
    
    print("=" * 50)
    print("🌐 URL Monitor Dashboard")
    print("=" * 50)
    print("📊 Acesse: http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)