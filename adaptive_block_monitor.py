import bettercam
import numpy as np
import time
import threading
import hashlib
import argparse
import tkinter as tk
import ctypes
import json
import os
from seed_growth_core import grow_seeds

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass


def get_block_hash(pixels):
    """Get a hash of pixel data for a block"""
    return hashlib.md5(pixels.tobytes()).hexdigest()


def get_all_block_hashes(screen_pixels, block_size):
    """Divide screen into blocks and get hash for each block"""
    height, width = screen_pixels.shape[:2]
    
    block_hashes = {}
    
    for y in range(0, height, block_size):
        for x in range(0, width, block_size):
            block_y_end = min(y + block_size, height)
            block_x_end = min(x + block_size, width)
            
            block_pixels = screen_pixels[y:block_y_end, x:block_x_end]
            block_key = (y // block_size, x // block_size)
            block_hashes[block_key] = get_block_hash(block_pixels)
    
    return block_hashes


def calculate_change_percentage(previous_hashes, current_hashes):
    """Calculate percentage of blocks that changed"""
    if not previous_hashes:
        return 0.0
    
    changed_count = 0
    total_count = len(current_hashes)
    
    for block_key in current_hashes:
        if block_key not in previous_hashes or previous_hashes[block_key] != current_hashes[block_key]:
            changed_count += 1
    
    percentage = (changed_count / total_count) * 100 if total_count > 0 else 0
    return percentage


class AdaptiveBlockMonitor:
    def __init__(self, args):
        self.seeds = args.seeds
        self.lookahead_pixels = args.lookahead_pixels
        self.wall_thickness = args.wall_thickness
        self.color_mode = args.color_mode
        self.no_overlap = args.no_overlap
        self.jitter = args.jitter
        self.growth_pixels = args.growth_pixels
        self.pixel_sample_rate = args.pixel_sample_rate
        self.block_size = args.block_size
        self.update_rate = args.update_rate
        self.change_threshold = args.change_threshold
        
        self.monitoring = True
        self.tracked_rect = None
        self.previous_hashes = None
        self.iteration = 0
        
        self.screen_width = 0
        self.screen_height = 0
        self.exclusion_center_width = 25
        self.exclusion_center_height = 33
        self.show_exclusion_zone = args.show_exclusion_zone
        
        # Create overlay window
        self.results_window = tk.Tk()
        self.results_window.attributes('-topmost', True)
        self.results_window.overrideredirect(True)
        self.results_window.attributes('-transparentcolor', 'white')
        
        self.results_window.bind('<Escape>', lambda e: self.stop())
        
        print(f"🎬 Starting adaptive block monitor")
        print(f"  Block size: {self.block_size}px")
        print(f"  Update rate: {self.update_rate}s")
        print(f"  Change threshold: {self.change_threshold}%")
        print(f"  Seeds: {self.seeds}, Keep: 1 (largest)")
        print(f"  Color mode: {self.color_mode}")
        print(f"  Press ESC to stop\n")
    
    def run(self):
        try:
            camera = bettercam.create(output_color="BGR")
            
            # Initial capture
            screen_capture = camera.grab()
            screen_pixels = np.array(screen_capture)
            screen_pixels = screen_pixels[:, :, [2, 1, 0]]
            
            screen_height, screen_width = screen_pixels.shape[:2]
            self.screen_width = screen_width
            self.screen_height = screen_height
            
            # Setup overlay window
            self.results_window.geometry(f"{screen_width}x{screen_height}+0+0")
            
            canvas = tk.Canvas(self.results_window, bg='white', highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            
            print("Performing initial seed growth search...")
            self._search_and_update(screen_pixels)
            self._update_canvas(canvas)
            self.results_window.deiconify()
            
            self.previous_hashes = get_all_block_hashes(screen_pixels, self.block_size)
            
            monitor_thread = threading.Thread(target=self._monitor_loop, args=(camera, canvas), daemon=True)
            monitor_thread.start()
            
            self.results_window.mainloop()
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.monitoring = False
            camera.release()
    
    def _monitor_loop(self, camera, canvas):
        try:
            while self.monitoring:
                time.sleep(self.update_rate)
                self.iteration += 1
                
                screen_capture = camera.grab()
                if screen_capture is None:
                    continue
                
                try:
                    screen_pixels = np.array(screen_capture)
                    if screen_pixels.ndim < 3:
                        continue
                    screen_pixels = screen_pixels[:, :, [2, 1, 0]]
                except (IndexError, ValueError):
                    continue
                
                current_hashes = get_all_block_hashes(screen_pixels, self.block_size)
                change_percentage = calculate_change_percentage(self.previous_hashes, current_hashes)
                
                print(f"[{self.iteration:03d}] {change_percentage:5.1f}% blocks changed")
                
                if change_percentage > self.change_threshold:
                    print(f"  → Threshold exceeded ({self.change_threshold}%), searching for new rectangle")
                    self._search_and_update(screen_pixels)
                
                self.results_window.after(0, lambda: self._update_canvas(canvas))
                self.previous_hashes = current_hashes
        
        except Exception as e:
            print(f"Monitor error: {e}")
    
    def _search_and_update(self, screen_pixels):
        try:
            # Calculate exclusion zone coordinates
            exclude_width = int(self.screen_width * self.exclusion_center_width / 100)
            exclude_height = int(self.screen_height * self.exclusion_center_height / 100)
            
            exclude_x1 = (self.screen_width - exclude_width) // 2
            exclude_y1 = (self.screen_height - exclude_height) // 2
            exclude_x2 = exclude_x1 + exclude_width
            exclude_y2 = exclude_y1 + exclude_height
            
            exclusion_zone = (exclude_x1, exclude_y1, exclude_x2, exclude_y2)
            
            results = grow_seeds(
                num_seeds=self.seeds,
                num_keep=1,
                screen_pixels=screen_pixels,
                lookahead_pixels=self.lookahead_pixels,
                wall_thickness=self.wall_thickness,
                color_mode=self.color_mode,
                jitter=self.jitter,
                growth_pixels=self.growth_pixels,
                pixel_sample_rate=self.pixel_sample_rate,
                no_overlap=self.no_overlap,
                exclusion_zone=exclusion_zone
            )
            
            if results:
                largest_coords, largest_area = results[0]
                self.tracked_rect = largest_coords
                print(f"  → Updated tracked rectangle: {largest_coords} ({largest_area} px²)")
        
        except Exception as e:
            print(f"Error searching: {e}")
    
    def _update_canvas(self, canvas):
        canvas.delete("all")
        
        # Draw exclusion zone (blue rectangle)
        if self.show_exclusion_zone and self.screen_width > 0 and self.screen_height > 0:
            exclude_width = int(self.screen_width * self.exclusion_center_width / 100)
            exclude_height = int(self.screen_height * self.exclusion_center_height / 100)
            
            exclude_x1 = (self.screen_width - exclude_width) // 2
            exclude_y1 = (self.screen_height - exclude_height) // 2
            exclude_x2 = exclude_x1 + exclude_width
            exclude_y2 = exclude_y1 + exclude_height
            
            canvas.create_rectangle(exclude_x1, exclude_y1, exclude_x2, exclude_y2, outline='blue', width=2, fill='')
        
        # Draw tracked rectangle (red)
        if self.tracked_rect is not None:
            x1, y1, x2, y2 = self.tracked_rect
            canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=3, fill='')
        
        self.results_window.update()

    def stop(self):
        self.monitoring = False
        self.results_window.destroy()


def load_config(config_path='config.json'):
    """Load configuration from JSON file"""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def main():
    config = load_config()
    
    parser = argparse.ArgumentParser(description='Adaptive block monitor with dynamic rectangle tracking')
    parser.add_argument('--config', type=str, default='config.json', help='Path to config file (default: config.json)')
    parser.add_argument('--seeds', type=int, default=config.get('seeds', 100), help='Number of seeds for growth')
    parser.add_argument('--lookahead-pixels', type=int, default=config.get('lookahead_pixels', 15), help='Lookahead pixels')
    parser.add_argument('--wall-thickness', type=int, default=config.get('wall_thickness', 5), help='Wall thickness')
    parser.add_argument('--color-mode', type=str, default=config.get('color_mode', 'average'), choices=['average', 'corners'], 
                        help='Color comparison mode')
    parser.add_argument('--no-overlap', action='store_true', default=config.get('no_overlap', False), help='Disable overlap detection')
    parser.add_argument('--jitter', type=int, default=config.get('jitter', 25), help='Jitter amount')
    parser.add_argument('--growth-pixels', type=int, default=config.get('growth_pixels', 5), help='Growth pixels per iteration')
    parser.add_argument('--pixel-sample-rate', type=int, default=config.get('pixel_sample_rate', 4), help='Pixel sample rate')
    parser.add_argument('--block-size', type=int, default=config.get('block_size', 10), help='Block size for change detection')
    parser.add_argument('--update-rate', type=float, default=config.get('update_rate', 1), help='Update rate in seconds')
    parser.add_argument('--change-threshold', type=float, default=config.get('change_threshold', 50.0), help='Percentage of blocks that must change to trigger a search')
    parser.add_argument('--exclude-center-width', type=int, default=config.get('exclude_center_width', 25), help='Percentage of screen width for exclusion center')
    parser.add_argument('--exclude-center-height', type=int, default=config.get('exclude_center_height', 33), help='Percentage of screen height for exclusion center')
    parser.add_argument('--show-exclusion-zone', action='store_true', default=config.get('show_exclusion_zone', False), help='Show the blue exclusion zone rectangle')
    
    args = parser.parse_args()
    
    monitor = AdaptiveBlockMonitor(args)
    monitor.exclusion_center_width = args.exclude_center_width
    monitor.exclusion_center_height = args.exclude_center_height
    monitor.run()


if __name__ == '__main__':
    main()
