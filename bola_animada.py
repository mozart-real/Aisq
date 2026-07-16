#!/usr/bin/env python3
import os
import sys
import time
import math

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def animate_ball():
    width = 40
    height = 15
    ball_char = 'o'
    
    # Posição inicial
    x = 5
    y = 7
    
    # Velocidade
    dx = 1
    dy = 1
    
    try:
        while True:
            # Limpar tela
            clear_screen()
            
            # Criar grid
            grid = [[' ' for _ in range(width)] for _ in range(height)]
            
            # Colocar a bola
            if 0 <= y < height and 0 <= x < width:
                grid[y][x] = ball_char
            
            # Atualizar posição
            x += dx
            y += dy
            
            # Verificar colisão com paredes horizontais
            if x <= 0 or x >= width - 1:
                dx = -dx
                x = max(0, min(x, width - 1))
            
            # Verificar colisão com paredes verticais
            if y <= 0 or y >= height - 1:
                dy = -dy
                y = max(0, min(y, height - 1))
            
            # Imprimir grid
            for row in grid:
                print(''.join(row))
            
            # Pequeno delay para animação suave
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nAnimação parada pelo usuário.")
        sys.exit(0)

if __name__ == "__main__":
    animate_ball()
