"""
MINES GAME - LED Floor Edition
40 players, elimination rounds, cyan animations
Uses the same ESP TCP server architecture
"""

import json
import socket
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import random
import logging

class MinesGame:
    def __init__(self):
        # Configuration
        self.config_file = 'C:\\Users\\prith\\Documents\\My Stuff\\Projects\\TILES\\version3\\esp_config.json'
        self.esp_port = 8080
        
        # ESP connections
        self.esp_sockets = {}
        self.esp_status = {}
        self.socket_lock = threading.Lock()
        
        # Load configuration
        self.load_config()
        
        # Game state
        self.current_round = 0
        self.game_active = False
        self.animation_active = True
        self.eliminated_tiles = set()  # Remember all eliminated tiles
        self.round_config = [
            {"round": 1, "eliminate": 10, "color": "red"},
            {"round": 2, "eliminate": 10, "color": "red"},
            {"round": 3, "eliminate": 5, "color": "red"},
            {"round": 4, "eliminate": 5, "color": "red"},
            {"round": 5, "eliminate": 3, "color": "red"},
            {"round": 6, "eliminate": 3, "color": "red"},
            {"round": 7, "eliminate": 2, "color": "red"},
            {"round": 8, "eliminate": 1, "color": "red"},  # 1 eliminated, 1 winner
        ]
        
        # Cyan animation
        self.animation_thread = None
        self.animation_position = 0
        
        # Setup logging
        self.setup_logging()
        
        # Create GUI
        self.create_gui()
        
    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler('mines_game.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*60)
        self.logger.info("MINES GAME - LED FLOOR EDITION")
        self.logger.info("="*60)
        
    def load_config(self):
        """Load ESP configuration"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            self.grid_rows = config['grid']['rows']
            self.grid_cols = config['grid']['cols']
            self.esp_map = config['esps']
            
            # Create tile to ESP mapping
            self.tile_to_esp = {}
            for mac, tiles in self.esp_map.items():
                for idx, tile_num in enumerate(tiles):
                    self.tile_to_esp[tile_num] = (mac, idx)
                    
            self.total_tiles = self.grid_rows * self.grid_cols
            
            print(f"✅ Loaded config: {self.grid_rows}x{self.grid_cols} grid ({self.total_tiles} tiles)")
            print(f"✅ {len(self.esp_map)} ESP32 controllers")
            
            # Initialize status
            for mac in self.esp_map.keys():
                self.esp_status[mac] = 'offline'
                
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            messagebox.showerror("Error", f"Error loading config: {e}")
            exit(1)
            
    def connect_to_esp(self, mac):
        """Connect to ESP"""
        try:
            hostname = f"esp-{mac}.local"
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((hostname, self.esp_port))
            
            self.logger.info(f"✅ Connected to {mac}")
            self.esp_status[mac] = 'online'
            
            if hasattr(self, 'root'):
                self.root.after(0, self.update_status_display)
            
            return sock
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to {mac}: {e}")
            self.esp_status[mac] = 'offline'
            return None
            
    def send_command(self, tile_num, command):
        """Send command to ESP"""
        if tile_num not in self.tile_to_esp:
            return False
            
        mac, local_idx = self.tile_to_esp[tile_num]
        
        with self.socket_lock:
            if mac not in self.esp_sockets or self.esp_sockets[mac] is None:
                self.esp_sockets[mac] = self.connect_to_esp(mac)
            
            sock = self.esp_sockets[mac]
            if not sock:
                return False
            
            try:
                cmd = f"T{local_idx + 1}_{command}\n"
                sock.sendall(cmd.encode())
                return True
                
            except Exception as e:
                self.logger.error(f"❌ Error sending to {mac}: {e}")
                try:
                    sock.close()
                except:
                    pass
                self.esp_sockets[mac] = None
                self.esp_status[mac] = 'offline'
                return False
                
    def set_tile_color(self, tile_num, r, g, b):
        """Set tile to specific RGB color"""
        if tile_num in self.eliminated_tiles:
            return  # Don't change eliminated tiles
        return self.send_command(tile_num, f"COLOR_{r}_{g}_{b}")
        
    def turn_off_tile(self, tile_num):
        """Turn off tile"""
        return self.send_command(tile_num, "OFF")
        
    def create_gui(self):
        """Create game GUI"""
        self.root = tk.Tk()
        self.root.title("MINES GAME - LED Floor Edition")
        self.root.geometry("1600x900")
        self.root.configure(bg='#1a1a1a')
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Left panel - Game grid
        left_frame = tk.Frame(main_frame, bg='#1a1a1a')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        # Right panel - Controls
        right_frame = tk.Frame(main_frame, bg='#2a2a2a', relief=tk.RAISED, bd=3)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        right_frame.config(width=400)
        
        self.create_game_grid(left_frame)
        self.create_control_panel(right_frame)
        
        # Auto-connect to ESPs
        threading.Thread(target=self.auto_connect_esps, daemon=True).start()
        
        # Start cyan animation
        self.start_cyan_animation()
        
    def create_game_grid(self, parent):
        """Create game grid - 10 columns x 4 rows"""
        grid_frame = tk.LabelFrame(
            parent,
            text=f"MINES GAME - {self.total_tiles} Players",
            bg='#2a2a2a',
            fg='#00ff00',
            font=('Arial', 16, 'bold'),
            padx=15,
            pady=15
        )
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tile_labels = {}
        
        # Create 10x4 grid (10 columns, 4 rows)
        tile_num = 1
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                label = tk.Label(
                    grid_frame,
                    text=str(tile_num),
                    width=7,
                    height=3,
                    bg='#00ffff',  # Cyan initially
                    fg='black',
                    font=('Arial', 14, 'bold'),
                    relief=tk.RAISED,
                    bd=3
                )
                label.grid(row=row, column=col, padx=3, pady=3, sticky='nsew')
                self.tile_labels[tile_num] = label
                tile_num += 1
                
        # Configure grid weights for responsive sizing
        for i in range(self.grid_cols):
            grid_frame.columnconfigure(i, weight=1)
        for i in range(self.grid_rows):
            grid_frame.rowconfigure(i, weight=1)
            
    def create_control_panel(self, parent):
        """Create control panel"""
        
        # Title
        title = tk.Label(
            parent,
            text="GAME CONTROL",
            bg='#2a2a2a',
            fg='#00ff00',
            font=('Arial', 20, 'bold')
        )
        title.pack(pady=15)
        
        # Game status frame
        status_frame = tk.LabelFrame(
            parent,
            text="Game Status",
            bg='#2a2a2a',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=15,
            pady=15
        )
        status_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Round display
        self.round_label = tk.Label(
            status_frame,
            text="Round: Ready to Start",
            bg='#2a2a2a',
            fg='#ffff00',
            font=('Arial', 14, 'bold')
        )
        self.round_label.pack(pady=5)
        
        # Players remaining
        self.players_label = tk.Label(
            status_frame,
            text=f"Players Remaining: {self.total_tiles}",
            bg='#2a2a2a',
            fg='#00ff00',
            font=('Arial', 12, 'bold')
        )
        self.players_label.pack(pady=5)
        
        # Eliminated this round
        self.eliminated_label = tk.Label(
            status_frame,
            text="Eliminated This Round: 0",
            bg='#2a2a2a',
            fg='#ff6666',
            font=('Arial', 12)
        )
        self.eliminated_label.pack(pady=5)
        
        # Game controls
        control_frame = tk.LabelFrame(
            parent,
            text="Controls",
            bg='#2a2a2a',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=15,
            pady=15
        )
        control_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Start game button
        self.start_btn = tk.Button(
            control_frame,
            text="▶ START GAME",
            command=self.start_game,
            bg='#00aa00',
            fg='white',
            font=('Arial', 14, 'bold'),
            height=2,
            relief=tk.RAISED,
            bd=4
        )
        self.start_btn.pack(fill=tk.X, pady=5)
        
        # Next round button
        self.next_round_btn = tk.Button(
            control_frame,
            text="➡ NEXT ROUND",
            command=self.next_round,
            bg='#ff8800',
            fg='white',
            font=('Arial', 14, 'bold'),
            height=2,
            relief=tk.RAISED,
            bd=4,
            state=tk.DISABLED
        )
        self.next_round_btn.pack(fill=tk.X, pady=5)
        
        # Reset button
        self.reset_btn = tk.Button(
            control_frame,
            text="🔄 RESET GAME",
            command=self.reset_game,
            bg='#cc0000',
            fg='white',
            font=('Arial', 12, 'bold'),
            height=2,
            relief=tk.RAISED,
            bd=4
        )
        self.reset_btn.pack(fill=tk.X, pady=5)
        
        # Round information
        info_frame = tk.LabelFrame(
            parent,
            text="Round Information",
            bg='#2a2a2a',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=10,
            pady=10
        )
        info_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Create scrollable text widget
        info_text = tk.Text(
            info_frame,
            bg='#1a1a1a',
            fg='#00ff00',
            font=('Courier', 9),
            height=12,
            wrap=tk.WORD,
            relief=tk.SUNKEN,
            bd=2
        )
        info_text.pack(fill=tk.BOTH, expand=True)
        
        info_content = """
ROUND ELIMINATION SCHEDULE:

Round 1: Eliminate 10 players
Round 2: Eliminate 10 players
         [20 remaining]

Round 3: Eliminate 5 players
Round 4: Eliminate 5 players
         [10 remaining]

Round 5: Eliminate 3 players
Round 6: Eliminate 3 players
         [4 remaining]

Round 7: Eliminate 2 players
         [2 remaining]

Round 8: Eliminate 1 player
         [1 WINNER!]

RED = Eliminated
GREEN = Winner
CYAN = Active players
        """
        info_text.insert('1.0', info_content)
        info_text.config(state=tk.DISABLED)
        
        # ESP status
        esp_frame = tk.LabelFrame(
            parent,
            text="ESP32 Status",
            bg='#2a2a2a',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=10,
            pady=10
        )
        esp_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.esp_status_label = tk.Label(
            esp_frame,
            text="Connecting...",
            bg='#2a2a2a',
            fg='#ffaa00',
            font=('Arial', 9)
        )
        self.esp_status_label.pack()
        
    def start_game(self):
        """Start the game"""
        if self.game_active:
            messagebox.showwarning("Game Active", "Game is already in progress!")
            return
            
        # Reset everything
        self.current_round = 0
        self.eliminated_tiles.clear()
        self.game_active = True
        
        # Stop animation
        self.animation_active = False
        time.sleep(0.3)  # Wait for animation to stop
        
        # Turn all tiles cyan
        for tile_num in range(1, self.total_tiles + 1):
            self.set_tile_color(tile_num, 0, 255, 255)  # Cyan
            self.tile_labels[tile_num].config(bg='#00ffff', fg='black')
            
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.next_round_btn.config(state=tk.NORMAL)
        self.round_label.config(text="Round: Ready - Press NEXT ROUND")
        self.players_label.config(text=f"Players Remaining: {self.total_tiles}")
        
        self.logger.info("🎮 Game started! All tiles cyan. Ready for Round 1.")
        messagebox.showinfo("Game Started", "Game started!\n\nAll 40 players are active.\n\nPress 'NEXT ROUND' to start Round 1.")
        
    def next_round(self):
        """Execute next round"""
        if not self.game_active:
            return
            
        if self.current_round >= len(self.round_config):
            messagebox.showinfo("Game Over", "Game has ended!")
            return
            
        # Get round configuration
        round_info = self.round_config[self.current_round]
        round_num = round_info['round']
        eliminate_count = round_info['eliminate']
        
        self.current_round += 1
        
        self.logger.info(f"🎯 Starting Round {round_num}")
        self.round_label.config(text=f"Round: {round_num} - Eliminating {eliminate_count} players...")
        
        # Get available tiles (not eliminated)
        available_tiles = [t for t in range(1, self.total_tiles + 1) if t not in self.eliminated_tiles]
        
        if len(available_tiles) < eliminate_count:
            messagebox.showerror("Error", "Not enough players remaining!")
            return
            
        # Randomly select tiles to eliminate
        tiles_to_eliminate = random.sample(available_tiles, eliminate_count)
        
        # Dramatic reveal - one by one
        for i, tile_num in enumerate(tiles_to_eliminate):
            time.sleep(0.3)  # Delay between eliminations
            
            # Turn tile red
            self.set_tile_color(tile_num, 255, 0, 0)  # Red
            self.tile_labels[tile_num].config(bg='#ff0000', fg='white')
            self.eliminated_tiles.add(tile_num)
            
            self.logger.info(f"❌ Eliminated tile {tile_num}")
            
        # Update status
        remaining = len(available_tiles) - eliminate_count
        self.players_label.config(text=f"Players Remaining: {remaining}")
        self.eliminated_label.config(text=f"Eliminated This Round: {eliminate_count}")
        
        # Check if this was the final round
        if self.current_round == len(self.round_config):
            # Game over - find the winner
            winner_tiles = [t for t in range(1, self.total_tiles + 1) if t not in self.eliminated_tiles]
            
            if len(winner_tiles) == 1:
                winner = winner_tiles[0]
                time.sleep(1)
                
                # Turn winner green and flash
                self.set_tile_color(winner, 0, 255, 0)  # Green
                self.tile_labels[winner].config(bg='#00ff00', fg='black')
                
                self.logger.info(f"🏆 WINNER: Tile {winner}")
                self.round_label.config(text=f"GAME OVER - WINNER: Tile {winner}!")
                
                # Flash winner tile
                threading.Thread(target=self.flash_winner, args=(winner,), daemon=True).start()
                
                messagebox.showinfo("WINNER!", f"🏆 GAME OVER! 🏆\n\nWINNER: Player on Tile {winner}!\n\nCongratulations!")
                
                self.next_round_btn.config(state=tk.DISABLED)
                self.game_active = False
            else:
                messagebox.showerror("Error", f"Expected 1 winner but found {len(winner_tiles)}")
        else:
            self.round_label.config(text=f"Round {round_num} Complete - {remaining} players remain")
            
    def flash_winner(self, tile_num):
        """Flash winner tile green"""
        for i in range(10):
            self.set_tile_color(tile_num, 0, 255, 0)  # Green
            time.sleep(0.3)
            self.set_tile_color(tile_num, 255, 255, 255)  # White
            time.sleep(0.3)
        self.set_tile_color(tile_num, 0, 255, 0)  # Green
        
    def reset_game(self):
        """Reset the game"""
        if self.game_active:
            response = messagebox.askyesno("Reset Game", "Are you sure you want to reset the game?")
            if not response:
                return
                
        self.logger.info("🔄 Resetting game")
        
        # Reset game state
        self.game_active = False
        self.current_round = 0
        self.eliminated_tiles.clear()
        
        # Turn off all tiles
        for tile_num in range(1, self.total_tiles + 1):
            self.turn_off_tile(tile_num)
            self.tile_labels[tile_num].config(bg='#3e3e3e', fg='white')
            
        time.sleep(0.5)
        
        # Restart cyan animation
        self.animation_active = True
        self.start_cyan_animation()
        
        # Reset UI
        self.start_btn.config(state=tk.NORMAL)
        self.next_round_btn.config(state=tk.DISABLED)
        self.round_label.config(text="Round: Ready to Start")
        self.players_label.config(text=f"Players Remaining: {self.total_tiles}")
        self.eliminated_label.config(text="Eliminated This Round: 0")
        
        self.logger.info("✅ Game reset complete")
        
    def start_cyan_animation(self):
        """Start cyan wave animation"""
        if self.animation_thread and self.animation_thread.is_alive():
            return
            
        self.animation_active = True
        self.animation_thread = threading.Thread(target=self.cyan_animation_loop, daemon=True)
        self.animation_thread.start()
        
    def cyan_animation_loop(self):
        """Cyan wave animation across all tiles"""
        self.logger.info("🌊 Starting cyan animation")
        
        while self.animation_active:
            try:
                # Create a wave effect - light up 5 tiles at a time
                for offset in range(self.total_tiles):
                    if not self.animation_active:
                        break
                        
                    for tile_num in range(1, self.total_tiles + 1):
                        if tile_num in self.eliminated_tiles:
                            continue
                            
                        # Calculate brightness based on position in wave
                        distance = abs((tile_num - 1) - (offset % self.total_tiles))
                        if distance > self.total_tiles // 2:
                            distance = self.total_tiles - distance
                            
                        if distance < 5:
                            brightness = int(255 * (1 - distance / 5))
                            self.set_tile_color(tile_num, 0, brightness, brightness)  # Cyan gradient
                            self.tile_labels[tile_num].config(
                                bg=f"#{0:02x}{brightness:02x}{brightness:02x}",
                                fg='black' if brightness > 128 else 'white'
                            )
                        else:
                            self.turn_off_tile(tile_num)
                            self.tile_labels[tile_num].config(bg='#1a1a1a', fg='#666666')
                            
                    time.sleep(0.1)  # Animation speed
                    
            except Exception as e:
                self.logger.error(f"Animation error: {e}")
                time.sleep(1)
                
        # Turn off all when animation stops
        for tile_num in range(1, self.total_tiles + 1):
            self.turn_off_tile(tile_num)
            
        self.logger.info("🌊 Cyan animation stopped")
        
    def auto_connect_esps(self):
        """Auto-connect to all ESPs"""
        self.logger.info("🔌 Connecting to ESPs...")
        time.sleep(1)
        
        for mac in self.esp_map.keys():
            self.connect_to_esp(mac)
            time.sleep(0.3)
            
        connected = sum(1 for s in self.esp_status.values() if s == 'online')
        self.logger.info(f"✅ Connected to {connected}/{len(self.esp_map)} ESPs")
        
        self.root.after(0, self.update_status_display)
        
    def update_status_display(self):
        """Update ESP status display"""
        online = sum(1 for s in self.esp_status.values() if s == 'online')
        total = len(self.esp_map)
        
        status_text = f"ESP32: {online}/{total} online"
        status_color = '#00ff00' if online == total else '#ffaa00' if online > 0 else '#ff0000'
        
        self.esp_status_label.config(text=status_text, fg=status_color)
        
    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        finally:
            self.animation_active = False
            with self.socket_lock:
                for sock in self.esp_sockets.values():
                    if sock:
                        try:
                            sock.close()
                        except:
                            pass

if __name__ == "__main__":
    print("="*60)
    print("MINES GAME - LED FLOOR EDITION")
    print("40 Players - Elimination Battle Royale")
    print("="*60)
    
    game = MinesGame()
    game.run()
