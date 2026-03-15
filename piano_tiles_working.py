"""
PIANO TILES - LED Floor Game - WORKING ARCHITECTURE
Uses proven TCP architecture from led_floor_master_WORKING__1_.py
Tile orientation from last.py (Row 0 = top, Row 9 = bottom)
"""

import json
import socket
import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import logging

class PianoTilesGame:
    def __init__(self):
        # Configuration
        self.config_file = 'C:\\Users\\prith\\Documents\\My Stuff\\Projects\\TILES\\version3\\esp_config.json'
        self.esp_port = 8080
        
        # ESP connections (socket cache) - Initialize BEFORE load_config
        self.esp_sockets = {}  # MAC -> socket
        self.esp_status = {}   # MAC -> 'online'/'offline'
        self.socket_lock = threading.Lock()
        
        # Setup logging
        self.setup_logging()
        
        # Load configuration
        self.load_config()
        
        # Game state
        self.game_active = False
        self.tile_color = (0, 255, 255)  # Cyan
        self.background_color = (50, 50, 50)  # Dim gray
        
        # Grid layout - 10 rows (top to bottom), 4 columns
        # Row 0 = top (tiles 37-40), Row 9 = bottom (tiles 1-4)
        self.grid_layout = [
            [37, 38, 39, 40],  # Row 0 - TOP
            [33, 34, 35, 36],  # Row 1
            [29, 30, 31, 32],  # Row 2
            [25, 26, 27, 28],  # Row 3
            [21, 22, 23, 24],  # Row 4
            [17, 18, 19, 20],  # Row 5
            [13, 14, 15, 16],  # Row 6
            [9, 10, 11, 12],   # Row 7
            [5, 6, 7, 8],      # Row 8
            [1, 2, 3, 4]       # Row 9 - BOTTOM
        ]
        
        # Active falling tiles: {column: [row_positions]}
        self.falling_tiles = {0: [], 1: [], 2: [], 3: []}
        self.tile_speed = 500  # ms between moves
        
        # Create GUI
        self.create_gui()
        
    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler('piano_tiles.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*60)
        self.logger.info("PIANO TILES - LED FLOOR GAME - WORKING MODE")
        self.logger.info("="*60)
        
    def load_config(self):
        """Load ESP configuration"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            self.grid_rows = config['grid']['rows']
            self.grid_cols = config['grid']['cols']
            self.esp_map = config['esps']  # MAC -> tile list
            
            # Create tile to ESP mapping: tile_num -> (mac, local_index)
            self.tile_to_esp = {}
            for mac, tiles in self.esp_map.items():
                for idx, tile_num in enumerate(tiles):
                    self.tile_to_esp[tile_num] = (mac, idx)
                    
            print(f"✅ Loaded config: {self.grid_rows}x{self.grid_cols} grid")
            print(f"✅ {len(self.esp_map)} ESP32 controllers")
            
            # Initialize status
            for mac in self.esp_map.keys():
                self.esp_status[mac] = 'offline'
                
        except FileNotFoundError:
            print(f"❌ Config file not found: {self.config_file}")
            exit(1)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            exit(1)
            
    def connect_to_esp(self, mac):
        """Connect to ESP via mDNS hostname"""
        try:
            hostname = f"esp-{mac}.local"
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((hostname, self.esp_port))
            
            self.logger.info(f"✅ Connected to {mac} ({hostname})")
            self.esp_status[mac] = 'online'
            
            # Update GUI
            if hasattr(self, 'root'):
                self.root.after(0, self.update_esp_status_gui)
            
            return sock
            
        except socket.gaierror:
            self.logger.error(f"❌ Cannot resolve {hostname} - check mDNS")
            self.esp_status[mac] = 'offline'
            return None
        except socket.timeout:
            self.logger.error(f"❌ Connection timeout to {hostname}")
            self.esp_status[mac] = 'offline'
            return None
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to {mac}: {e}")
            self.esp_status[mac] = 'offline'
            return None
            
    def send_command(self, tile_num, command):
        """Send command to ESP controlling the tile"""
        if tile_num not in self.tile_to_esp:
            self.logger.warning(f"⚠️  Tile {tile_num} not in configuration")
            return False
            
        mac, local_idx = self.tile_to_esp[tile_num]
        
        with self.socket_lock:
            # Get or create connection
            if mac not in self.esp_sockets or self.esp_sockets[mac] is None:
                self.esp_sockets[mac] = self.connect_to_esp(mac)
            
            sock = self.esp_sockets[mac]
            if not sock:
                return False
            
            try:
                # Command format: T<local_tile>_<action>
                cmd = f"T{local_idx + 1}_{command}\n"
                sock.sendall(cmd.encode())
                return True
                
            except Exception as e:
                self.logger.error(f"❌ Error sending to {mac}: {e}")
                # Close dead socket
                try:
                    sock.close()
                except:
                    pass
                self.esp_sockets[mac] = None
                self.esp_status[mac] = 'offline'
                
                # Update GUI
                if hasattr(self, 'root'):
                    self.root.after(0, self.update_esp_status_gui)
                
                return False
                
    def set_tile_color(self, tile_num, r, g, b):
        """Set tile to specific RGB color"""
        return self.send_command(tile_num, f"COLOR_{r}_{g}_{b}")
        
    def turn_off_tile(self, tile_num):
        """Turn off tile"""
        return self.send_command(tile_num, "OFF")
        
    def set_all_tiles_background(self):
        """Set all tiles to background color"""
        r, g, b = self.background_color
        for row in range(10):
            for col in range(4):
                tile_num = self.grid_layout[row][col]
                self.set_tile_color(tile_num, r, g, b)
                bg_hex = f"#{r:02x}{g:02x}{b:02x}"
                if hasattr(self, 'tile_labels'):
                    self.root.after(0, lambda t=tile_num, c=bg_hex: 
                                   self.tile_labels[t].config(bg=c, fg='#666666'))
                                   
    def create_gui(self):
        """Create GUI"""
        self.root = tk.Tk()
        self.root.title("Piano Tiles - LED Floor Game (WORKING)")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1e1e1e')
        
        # Main layout
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left - Game grid
        left_frame = tk.Frame(main_frame, bg='#1e1e1e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Right - Controls
        right_frame = tk.Frame(main_frame, bg='#2e2e2e', relief=tk.RAISED, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        self.create_grid_display(left_frame)
        self.create_control_panel(right_frame)
        
        # Auto-connect to ESPs
        threading.Thread(target=self.auto_connect_esps, daemon=True).start()
        
        # Initialize all tiles to background color
        self.root.after(1000, self.set_all_tiles_background)
        
    def create_grid_display(self, parent):
        """Create LED floor grid visualization - 10 rows x 4 columns"""
        grid_frame = tk.LabelFrame(
            parent,
            text="LED Floor - Piano Tiles (Top ↓ Bottom)",
            bg='#2e2e2e',
            fg='#00ff00',
            font=('Arial', 14, 'bold'),
            padx=10,
            pady=10
        )
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tile_labels = {}
        
        # Create grid - 10 rows (top to bottom), 4 columns
        for row in range(10):
            for col in range(4):
                tile_num = self.grid_layout[row][col]
                
                label = tk.Label(
                    grid_frame,
                    text=str(tile_num),
                    width=15,
                    height=4,
                    bg='#2a2a2a',
                    fg='#666666',
                    font=('Arial', 16, 'bold'),
                    relief=tk.RAISED,
                    bd=3
                )
                label.grid(row=row, column=col, padx=3, pady=3, sticky='nsew')
                self.tile_labels[tile_num] = label
                
        # Configure grid weights
        for i in range(4):
            grid_frame.columnconfigure(i, weight=1)
        for i in range(10):
            grid_frame.rowconfigure(i, weight=1)
            
    def create_control_panel(self, parent):
        """Create control panel"""
        
        # Title
        tk.Label(
            parent,
            text="Game Controls",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 16, 'bold')
        ).pack(pady=10)
        
        # Game controls frame
        game_frame = tk.LabelFrame(
            parent,
            text="Game",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        game_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Start/Stop button
        self.start_btn = tk.Button(
            game_frame,
            text="▶ START GAME",
            command=self.toggle_game,
            bg='#00aa00',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=20,
            height=2
        )
        self.start_btn.pack(pady=5)
        
        # Test button
        tk.Button(
            game_frame,
            text="🔦 Test All Tiles",
            command=self.test_all_tiles,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=20
        ).pack(pady=5)
        
        # Speed controls
        speed_frame = tk.LabelFrame(
            parent,
            text="Speed Control",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        speed_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.speed_label = tk.Label(
            speed_frame,
            text=f"Speed: {self.tile_speed} ms",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10)
        )
        self.speed_label.pack()
        
        self.speed_slider = tk.Scale(
            speed_frame,
            from_=100,
            to=1000,
            orient=tk.HORIZONTAL,
            bg='#2e2e2e',
            fg='white',
            highlightthickness=0,
            command=self.update_speed
        )
        self.speed_slider.set(self.tile_speed)
        self.speed_slider.pack(fill=tk.X, pady=5)
        
        # Speed presets
        preset_frame = tk.Frame(speed_frame, bg='#2e2e2e')
        preset_frame.pack()
        
        tk.Button(
            preset_frame,
            text="Fast",
            command=lambda: self.set_speed(200),
            bg='#444444',
            fg='white',
            width=6
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            preset_frame,
            text="Medium",
            command=lambda: self.set_speed(500),
            bg='#444444',
            fg='white',
            width=6
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            preset_frame,
            text="Slow",
            command=lambda: self.set_speed(800),
            bg='#444444',
            fg='white',
            width=6
        ).pack(side=tk.LEFT, padx=2)
        
        # Color controls
        color_frame = tk.LabelFrame(
            parent,
            text="Tile Color",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        color_frame.pack(fill=tk.X, padx=10, pady=5)
        
        colors = [
            ("Cyan", (0, 255, 255)),
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Purple", (255, 0, 255))
        ]
        
        for name, rgb in colors:
            r, g, b = rgb
            tk.Button(
                color_frame,
                text=name,
                command=lambda c=rgb: self.set_color(c),
                bg=f"#{r:02x}{g:02x}{b:02x}",
                fg='white' if sum(rgb) < 400 else 'black',
                width=18
            ).pack(pady=2)
            
        # ESP Status
        esp_frame = tk.LabelFrame(
            parent,
            text="ESP32 Status",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        esp_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Scrollable area
        canvas = tk.Canvas(esp_frame, bg='#2e2e2e', highlightthickness=0)
        scrollbar = tk.Scrollbar(esp_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.esp_status_frame = tk.Frame(canvas, bg='#2e2e2e')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=self.esp_status_frame, anchor='nw')
        
        self.esp_status_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        # Reconnect button
        tk.Button(
            parent,
            text="🔄 Reconnect All ESPs",
            command=self.reconnect_all,
            bg='#5bc0de',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=20
        ).pack(padx=10, pady=5)
        
        # Stats
        self.stats_label = tk.Label(
            parent,
            text="0/10 online",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 9)
        )
        self.stats_label.pack(padx=10, pady=5)
        
    def test_all_tiles(self):
        """Test all tiles by lighting them up briefly"""
        self.logger.info("🔦 Testing all tiles...")
        
        def test():
            # Light all tiles
            r, g, b = self.tile_color
            for tile_num in range(1, 41):
                self.set_tile_color(tile_num, r, g, b)
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                self.root.after(0, lambda t=tile_num, c=color_hex: 
                               self.tile_labels[t].config(bg=c, fg='black'))
            
            time.sleep(2)
            
            # Turn all off
            self.set_all_tiles_background()
        
        threading.Thread(target=test, daemon=True).start()
        
    def toggle_game(self):
        """Start/stop the game"""
        if self.game_active:
            self.stop_game()
        else:
            self.start_game()
            
    def start_game(self):
        """Start the game"""
        self.game_active = True
        self.start_btn.config(text="⏸ STOP GAME", bg='#cc0000')
        self.logger.info("🎮 Game started")
        
        # Clear falling tiles
        for col in range(4):
            self.falling_tiles[col] = []
        
        # Start game loop
        threading.Thread(target=self.game_loop, daemon=True).start()
        
    def stop_game(self):
        """Stop the game"""
        self.game_active = False
        self.start_btn.config(text="▶ START GAME", bg='#00aa00')
        self.logger.info("⏸ Game stopped")
        
        # Clear all tiles
        time.sleep(0.2)
        self.set_all_tiles_background()
        
    def game_loop(self):
        """Main game loop"""
        last_spawn = time.time()
        spawn_interval = 1.5  # Spawn new tile every 1.5 seconds
        
        while self.game_active:
            try:
                current_time = time.time()
                
                # Spawn new tiles randomly
                if current_time - last_spawn >= spawn_interval:
                    col = random.randint(0, 3)
                    if len(self.falling_tiles[col]) == 0 or self.falling_tiles[col][-1] > 2:
                        self.falling_tiles[col].append(0)  # Start at top row
                        self.logger.info(f"🎯 Spawned tile in column {col}")
                    last_spawn = current_time
                
                # Update all falling tiles
                self.update_falling_tiles()
                
                # Wait for speed interval
                time.sleep(self.tile_speed / 1000.0)
                
            except Exception as e:
                self.logger.error(f"Game loop error: {e}")
                time.sleep(0.5)
                
    def update_falling_tiles(self):
        """Update positions of all falling tiles"""
        r, g, b = self.tile_color
        bg_r, bg_g, bg_b = self.background_color
        
        for col in range(4):
            new_positions = []
            
            for row in self.falling_tiles[col]:
                # Clear current position
                tile_num = self.grid_layout[row][col]
                self.set_tile_color(tile_num, bg_r, bg_g, bg_b)
                bg_hex = f"#{bg_r:02x}{bg_g:02x}{bg_b:02x}"
                self.root.after(0, lambda t=tile_num, c=bg_hex: 
                               self.tile_labels[t].config(bg=c, fg='#666666'))
                
                # Move down
                new_row = row + 1
                
                # If still on grid, keep it
                if new_row < 10:
                    new_positions.append(new_row)
                    
                    # Light up new position
                    new_tile_num = self.grid_layout[new_row][col]
                    self.set_tile_color(new_tile_num, r, g, b)
                    color_hex = f"#{r:02x}{g:02x}{b:02x}"
                    self.root.after(0, lambda t=new_tile_num, c=color_hex: 
                                   self.tile_labels[t].config(bg=c, fg='black'))
                else:
                    # Tile reached bottom
                    self.logger.info(f"🎯 Tile reached bottom in column {col}")
            
            self.falling_tiles[col] = new_positions
            
    def update_speed(self, value):
        """Update speed from slider"""
        self.tile_speed = int(float(value))
        self.speed_label.config(text=f"Speed: {self.tile_speed} ms")
        
    def set_speed(self, speed):
        """Set speed to preset"""
        self.tile_speed = speed
        self.speed_slider.set(speed)
        self.speed_label.config(text=f"Speed: {self.tile_speed} ms")
        
    def set_color(self, color):
        """Set tile color"""
        self.tile_color = color
        r, g, b = color
        self.logger.info(f"🎨 Color changed to RGB({r}, {g}, {b})")
        
    def auto_connect_esps(self):
        """Auto-connect to all ESPs on startup"""
        self.logger.info("🔌 Connecting to ESPs...")
        time.sleep(1)  # Wait for GUI to load
        
        for mac in self.esp_map.keys():
            self.connect_to_esp(mac)
            time.sleep(0.5)
            
        connected = sum(1 for s in self.esp_status.values() if s == 'online')
        self.logger.info(f"✅ Connected to {connected}/{len(self.esp_map)} ESPs")
        
        self.root.after(0, self.update_esp_status_gui)
        
    def reconnect_all(self):
        """Reconnect to all ESPs"""
        def reconnect():
            self.logger.info("🔄 Reconnecting to all ESPs...")
            with self.socket_lock:
                # Close existing connections
                for sock in self.esp_sockets.values():
                    if sock:
                        try:
                            sock.close()
                        except:
                            pass
                self.esp_sockets.clear()
                
            # Reconnect
            for mac in self.esp_map.keys():
                self.connect_to_esp(mac)
                time.sleep(0.5)
                
            self.root.after(0, self.update_esp_status_gui)
            
        threading.Thread(target=reconnect, daemon=True).start()
        
    def update_esp_status_gui(self):
        """Update ESP status display"""
        # Clear
        for widget in self.esp_status_frame.winfo_children():
            widget.destroy()
            
        # Create status for each ESP
        for mac, tiles in self.esp_map.items():
            frame = tk.Frame(self.esp_status_frame, bg='#3e3e3e', relief=tk.RAISED, bd=1)
            frame.pack(fill=tk.X, pady=2, padx=2)
            
            # MAC (short)
            tk.Label(
                frame,
                text=f"{mac[-6:]}",
                bg='#3e3e3e',
                fg='white',
                font=('Arial', 9, 'bold'),
                width=8,
                anchor='w'
            ).pack(side=tk.LEFT, padx=5)
            
            # Status
            status = self.esp_status.get(mac, 'offline')
            status_text = "🟢 ON" if status == 'online' else "🔴 OFF"
            status_color = '#5cb85c' if status == 'online' else '#d9534f'
            
            tk.Label(
                frame,
                text=status_text,
                bg=status_color,
                fg='white',
                font=('Arial', 8, 'bold'),
                width=8
            ).pack(side=tk.LEFT, padx=5)
            
            # Tiles
            tk.Label(
                frame,
                text=f"Tiles: {tiles}",
                bg='#3e3e3e',
                fg='white',
                font=('Arial', 8),
                anchor='w'
            ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
        self.update_stats()
        
    def update_stats(self):
        """Update stats"""
        esps_online = sum(1 for s in self.esp_status.values() if s == 'online')
        total_esps = len(self.esp_map)
        
        self.stats_label.config(
            text=f"{esps_online}/{total_esps} online"
        )
        
    def run(self):
        """Run application"""
        try:
            self.root.mainloop()
        finally:
            self.game_active = False
            # Cleanup
            with self.socket_lock:
                for sock in self.esp_sockets.values():
                    if sock:
                        try:
                            sock.close()
                        except:
                            pass

if __name__ == "__main__":
    print("="*60)
    print("PIANO TILES - LED FLOOR GAME - WORKING ARCHITECTURE")
    print("="*60)
    
    game = PianoTilesGame()
    game.run()
