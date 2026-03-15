"""
LED Floor Master Controller - WORKING ARCHITECTURE
Matches your proven TCP server architecture
Supports WS2812B LED strips with color control
"""

import json
import socket
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
import threading
import time
import logging

class LEDFloorMaster:
    def __init__(self):
        # Configuration
        self.config_file = 'C:\\Users\\prith\\Documents\\My Stuff\\Projects\\TILES\\version3\\esp_config.json'
        self.esp_port = 8080
        
        # ESP connections (socket cache) - Initialize BEFORE load_config
        self.esp_sockets = {}  # MAC -> socket
        self.esp_status = {}   # MAC -> 'online'/'offline'
        self.socket_lock = threading.Lock()
        
        # Tile states
        self.tile_states = {}  # tile_num -> (r, g, b) or None
        self.selected_color = (0, 255, 0)  # Default green
        
        # Setup logging
        self.setup_logging()
        
        # Load configuration (needs esp_status to exist)
        self.load_config()
        
        # Create GUI
        self.create_gui()
        
    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler('led_floor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*60)
        self.logger.info("LED Floor Master Controller - WORKING MODE")
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
            messagebox.showerror("Error", f"Config file not found: {self.config_file}")
            exit(1)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            messagebox.showerror("Error", f"Error loading config: {e}")
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
                # local_tile is 1-4 (the tile index on this specific ESP)
                cmd = f"T{local_idx + 1}_{command}\n"
                sock.sendall(cmd.encode())
                self.logger.info(f"📤 Sent to tile {tile_num}: {cmd.strip()}")
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
                
    def create_gui(self):
        """Create GUI"""
        self.root = tk.Tk()
        self.root.title("LED Floor Master - 40 Tiles (10x4)")
        self.root.geometry("1400x800")
        self.root.configure(bg='#1e1e1e')
        
        # Main layout
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left - Tile grid
        left_frame = tk.Frame(main_frame, bg='#1e1e1e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Right - Controls
        right_frame = tk.Frame(main_frame, bg='#2e2e2e', relief=tk.RAISED, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        self.create_tile_grid(left_frame)
        self.create_control_panel(right_frame)
        
        # Auto-connect to ESPs
        threading.Thread(target=self.auto_connect_esps, daemon=True).start()
        
    def create_tile_grid(self, parent):
        """Create tile grid"""
        grid_frame = tk.LabelFrame(
            parent,
            text=f"LED Floor ({self.grid_rows}x{self.grid_cols})",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=10,
            pady=10
        )
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tile_buttons = {}
        
        tile_num = 1
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                btn = tk.Button(
                    grid_frame,
                    text=str(tile_num),
                    width=6,
                    height=3,
                    bg='#3e3e3e',
                    fg='white',
                    font=('Arial', 14, 'bold'),
                    relief=tk.RAISED,
                    bd=3,
                    command=lambda t=tile_num: self.tile_clicked(t)
                )
                btn.grid(row=row, column=col, padx=2, pady=2, sticky='nsew')
                self.tile_buttons[tile_num] = btn
                tile_num += 1
                
        # Configure grid weights
        for i in range(self.grid_cols):
            grid_frame.columnconfigure(i, weight=1)
        for i in range(self.grid_rows):
            grid_frame.rowconfigure(i, weight=1)
            
    def create_control_panel(self, parent):
        """Create control panel"""
        
        # Title
        tk.Label(
            parent,
            text="Control Panel",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 16, 'bold')
        ).pack(pady=10)
        
        # Color selector
        color_frame = tk.LabelFrame(
            parent,
            text="Color Selection",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        color_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Color preview
        self.color_preview = tk.Canvas(
            color_frame,
            width=200,
            height=50,
            bg=self.rgb_to_hex(self.selected_color),
            relief=tk.SUNKEN,
            bd=3
        )
        self.color_preview.pack(pady=5)
        
        # Color picker button
        tk.Button(
            color_frame,
            text="Choose Color",
            command=self.choose_color,
            bg='#4e4e4e',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=20
        ).pack(pady=5)
        
        # Preset colors
        preset_frame = tk.Frame(color_frame, bg='#2e2e2e')
        preset_frame.pack(fill=tk.X, pady=5)
        
        presets = [
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Cyan", (0, 255, 255)),
            ("Magenta", (255, 0, 255)),
            ("White", (255, 255, 255)),
            ("Orange", (255, 165, 0))
        ]
        
        for i, (name, color) in enumerate(presets):
            btn = tk.Button(
                preset_frame,
                text=name,
                bg=self.rgb_to_hex(color),
                fg='black' if sum(color) > 400 else 'white',
                width=8,
                command=lambda c=color: self.set_color(c)
            )
            btn.grid(row=i//4, column=i%4, padx=2, pady=2)
            
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
        
        # Controls
        control_frame = tk.LabelFrame(
            parent,
            text="Controls",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=10
        )
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(
            control_frame,
            text="Clear All",
            command=self.clear_all,
            bg='#d9534f',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=20
        ).pack(pady=2)
        
        tk.Button(
            control_frame,
            text="Reconnect All",
            command=self.reconnect_all,
            bg='#5bc0de',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=20
        ).pack(pady=2)
        
        # Stats
        self.stats_label = tk.Label(
            parent,
            text="Stats: 0/40 ON | 0/10 online",
            bg='#2e2e2e',
            fg='white',
            font=('Arial', 9)
        )
        self.stats_label.pack(padx=10, pady=5)
        
    def choose_color(self):
        """Open color picker"""
        color = colorchooser.askcolor(
            title="Choose Color",
            initialcolor=self.rgb_to_hex(self.selected_color)
        )
        if color[0]:
            self.set_color(tuple(int(c) for c in color[0]))
            
    def set_color(self, rgb):
        """Set selected color"""
        self.selected_color = rgb
        self.color_preview.config(bg=self.rgb_to_hex(rgb))
        self.logger.info(f"🎨 Selected: RGB{rgb}")
        
    def rgb_to_hex(self, rgb):
        """Convert RGB to hex"""
        return "#{:02x}{:02x}{:02x}".format(*rgb)
        
    def tile_clicked(self, tile_num):
        """Handle tile click"""
        if tile_num in self.tile_states:
            # Turn OFF
            self.set_tile_color(tile_num, None)
        else:
            # Turn ON with selected color
            self.set_tile_color(tile_num, self.selected_color)
            
    def set_tile_color(self, tile_num, color):
        """Set tile color"""
        if color:
            r, g, b = color
            command = f"COLOR_{r}_{g}_{b}"
            
            if self.send_command(tile_num, command):
                self.tile_states[tile_num] = color
                self.tile_buttons[tile_num].config(bg=self.rgb_to_hex(color))
                self.update_stats()
        else:
            command = "OFF"
            
            if self.send_command(tile_num, command):
                if tile_num in self.tile_states:
                    del self.tile_states[tile_num]
                self.tile_buttons[tile_num].config(bg='#3e3e3e')
                self.update_stats()
                
    def clear_all(self):
        """Turn off all tiles"""
        for tile_num in list(self.tile_states.keys()):
            self.set_tile_color(tile_num, None)
        self.logger.info("🧹 Cleared all tiles")
        
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
        tiles_on = len(self.tile_states)
        total_tiles = self.grid_rows * self.grid_cols
        esps_online = sum(1 for s in self.esp_status.values() if s == 'online')
        total_esps = len(self.esp_map)
        
        self.stats_label.config(
            text=f"Stats: {tiles_on}/{total_tiles} ON | {esps_online}/{total_esps} online"
        )
        
    def run(self):
        """Run application"""
        try:
            self.root.mainloop()
        finally:
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
    print("LED FLOOR MASTER - WORKING ARCHITECTURE")
    print("="*60)
    
    app = LEDFloorMaster()
    app.run()
