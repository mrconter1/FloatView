from dataclasses import dataclass
import numpy as np
from numba import jit
import time

@jit(nopython=True)
def compare_avg_color_numba(current_pixels, next_pixels, sample_rate):
    h1, w1 = current_pixels.shape[0], current_pixels.shape[1]
    h2, w2 = next_pixels.shape[0], next_pixels.shape[1]
    
    r1, g1, b1, count1 = 0, 0, 0, 0
    for i in range(0, h1, sample_rate):
        for j in range(0, w1, sample_rate):
            r1 += current_pixels[i, j, 0]
            g1 += current_pixels[i, j, 1]
            b1 += current_pixels[i, j, 2]
            count1 += 1
    
    r2, g2, b2, count2 = 0, 0, 0, 0
    for i in range(0, h2, sample_rate):
        for j in range(0, w2, sample_rate):
            r2 += next_pixels[i, j, 0]
            g2 += next_pixels[i, j, 1]
            b2 += next_pixels[i, j, 2]
            count2 += 1
    
    if count1 == 0 or count2 == 0:
        return False
    
    return (r1 // count1 != r2 // count2) or (g1 // count1 != g2 // count2) or (b1 // count1 != b2 // count2)


@jit(nopython=True)
def compare_corner_horizontal_numba(current_pixels, next_pixels, sample_rate):
    h1, w1 = current_pixels.shape[0], current_pixels.shape[1]
    h2, w2 = next_pixels.shape[0], next_pixels.shape[1]
    
    current_edge = np.zeros((w1, 3), dtype=np.uint8)
    for j in range(w1):
        r_sum, g_sum, b_sum, count = 0, 0, 0, 0
        for i in range(h1):
            r_sum += current_pixels[i, j, 0]
            g_sum += current_pixels[i, j, 1]
            b_sum += current_pixels[i, j, 2]
            count += 1
        if count > 0:
            current_edge[j, 0] = r_sum // count
            current_edge[j, 1] = g_sum // count
            current_edge[j, 2] = b_sum // count
    
    next_edge = np.zeros((w2, 3), dtype=np.uint8)
    for j in range(w2):
        r_sum, g_sum, b_sum, count = 0, 0, 0, 0
        for i in range(h2):
            r_sum += next_pixels[i, j, 0]
            g_sum += next_pixels[i, j, 1]
            b_sum += next_pixels[i, j, 2]
            count += 1
        if count > 0:
            next_edge[j, 0] = r_sum // count
            next_edge[j, 1] = g_sum // count
            next_edge[j, 2] = b_sum // count
    
    corner_indices = [0, w1 // 2, w1 - 1]
    for idx in corner_indices:
        if (current_edge[idx, 0] != next_edge[idx, 0] or
            current_edge[idx, 1] != next_edge[idx, 1] or
            current_edge[idx, 2] != next_edge[idx, 2]):
            return True
    
    return False


@jit(nopython=True)
def compare_corner_vertical_numba(current_pixels, next_pixels, sample_rate):
    h1, w1 = current_pixels.shape[0], current_pixels.shape[1]
    h2, w2 = next_pixels.shape[0], next_pixels.shape[1]
    
    current_edge = np.zeros((h1, 3), dtype=np.uint8)
    for i in range(h1):
        r_sum, g_sum, b_sum, count = 0, 0, 0, 0
        for j in range(w1):
            r_sum += current_pixels[i, j, 0]
            g_sum += current_pixels[i, j, 1]
            b_sum += current_pixels[i, j, 2]
            count += 1
        if count > 0:
            current_edge[i, 0] = r_sum // count
            current_edge[i, 1] = g_sum // count
            current_edge[i, 2] = b_sum // count
    
    next_edge = np.zeros((h2, 3), dtype=np.uint8)
    for i in range(h2):
        r_sum, g_sum, b_sum, count = 0, 0, 0, 0
        for j in range(w2):
            r_sum += next_pixels[i, j, 0]
            g_sum += next_pixels[i, j, 1]
            b_sum += next_pixels[i, j, 2]
            count += 1
        if count > 0:
            next_edge[i, 0] = r_sum // count
            next_edge[i, 1] = g_sum // count
            next_edge[i, 2] = b_sum // count
    
    corner_indices = [0, h1 // 2, h1 - 1]
    for idx in corner_indices:
        if (current_edge[idx, 0] != next_edge[idx, 0] or
            current_edge[idx, 1] != next_edge[idx, 1] or
            current_edge[idx, 2] != next_edge[idx, 2]):
            return True
    
    return False


@dataclass
class Config:
    aspect_ratio: float = 16 / 9
    lookahead_pixels: int = 1
    wall_thickness: int = 1
    color_mode: str = 'corners'
    jitter: int = 0
    growth_pixels: int = 1
    pixel_sample_rate: int = 1


class Seed:
    def __init__(self, center_x: int, center_y: int, config: Config, screen_pixels: np.ndarray, seed_id: int, compare_func, exclusion_zone=None):
        initial_size = 5
        self.x1 = center_x
        self.y1 = center_y
        self.x2 = center_x + int(initial_size * config.aspect_ratio)
        self.y2 = center_y + initial_size
        
        self.config = config
        self.screen_pixels = screen_pixels
        self.seed_id = seed_id
        self.growth_complete = False
        self.compare_func = compare_func
        
        self.screen_height, self.screen_width = screen_pixels.shape[:2]
        
        self.lock_left = False
        self.lock_right = False
        self.lock_top = False
        self.lock_bottom = False
        
        # Exclusion zone: (x1, y1, x2, y2) or None
        self.exclusion_zone = exclusion_zone
    
    def get_coords(self):
        return (self.x1, self.y1, self.x2, self.y2)
    
    def get_area(self):
        return max(0, (self.x2 - self.x1) * (self.y2 - self.y1))
    
    def grow(self):
        if self.growth_complete:
            return
        
        growth_pixels = self.config.growth_pixels
        
        if self.lock_left and self.lock_right:
            return
        if self.lock_top and self.lock_bottom:
            return
        
        if not self.lock_top and not self.lock_bottom:
            self.y1 -= growth_pixels
            self.y2 += growth_pixels
        elif not self.lock_top:
            self.y1 -= growth_pixels * 2
        elif not self.lock_bottom:
            self.y2 += growth_pixels * 2
        
        current_height = self.y2 - self.y1
        target_width = int(current_height * self.config.aspect_ratio)
        current_width = self.x2 - self.x1
        width_diff = target_width - current_width
        
        if not self.lock_left and not self.lock_right:
            self.x1 -= width_diff // 2
            self.x2 += width_diff - (width_diff // 2)
        elif not self.lock_left:
            self.x1 -= width_diff
        elif not self.lock_right:
            self.x2 += width_diff
        
        self.x1 = max(0, self.x1)
        self.y1 = max(0, self.y1)
        self.x2 = min(self.screen_width, self.x2)
        self.y2 = min(self.screen_height, self.y2)
        
        # Clip to exclusion zone boundaries
        if self.exclusion_zone is not None:
            ex_x1, ex_y1, ex_x2, ex_y2 = self.exclusion_zone
            
            # If left edge has crossed into zone from outside-left, push it back
            if self.x1 < ex_x1 and self.x2 > ex_x1:
                self.x1 = ex_x1
            
            # If right edge has crossed into zone from outside-right, push it back
            if self.x2 > ex_x2 and self.x1 < ex_x2:
                self.x2 = ex_x2
            
            # If top edge has crossed into zone from outside-top, push it back
            if self.y1 < ex_y1 and self.y2 > ex_y1:
                self.y1 = ex_y1
            
            # If bottom edge has crossed into zone from outside-bottom, push it back
            if self.y2 > ex_y2 and self.y1 < ex_y2:
                self.y2 = ex_y2
    
    def _get_wall_pixels(self, wall: str):
        thickness = self.config.wall_thickness
        
        if wall == 'top':
            return self.screen_pixels[self.y1:self.y1+thickness, self.x1:self.x2]
        elif wall == 'bottom':
            return self.screen_pixels[self.y2-thickness:self.y2, self.x1:self.x2]
        elif wall == 'left':
            return self.screen_pixels[self.y1:self.y2, self.x1:self.x1+thickness]
        elif wall == 'right':
            return self.screen_pixels[self.y1:self.y2, self.x2-thickness:self.x2]
        return None
    
    def _get_next_wall_pixels(self, wall: str, growth_pixels: int):
        screen_height, screen_width = self.screen_pixels.shape[:2]
        thickness = self.config.wall_thickness
        
        if wall == 'top':
            next_y = max(0, self.y1 - growth_pixels)
            if next_y == self.y1:
                return None
            return self.screen_pixels[next_y:next_y+thickness, self.x1:self.x2]
        elif wall == 'bottom':
            next_y = min(screen_height, self.y2 + growth_pixels)
            if next_y == self.y2:
                return None
            return self.screen_pixels[next_y-thickness:next_y, self.x1:self.x2]
        elif wall == 'left':
            next_x = max(0, self.x1 - growth_pixels)
            if next_x == self.x1:
                return None
            return self.screen_pixels[self.y1:self.y2, next_x:next_x+thickness]
        elif wall == 'right':
            next_x = min(screen_width, self.x2 + growth_pixels)
            if next_x == self.x2:
                return None
            return self.screen_pixels[self.y1:self.y2, next_x-thickness:next_x]
        return None
    
    def check_and_lock_walls(self, sample_rate: int):
        screen_height, screen_width = self.screen_pixels.shape[:2]
        
        walls_to_check = []
        if not self.lock_top:
            walls_to_check.append('top')
        if not self.lock_bottom:
            walls_to_check.append('bottom')
        if not self.lock_left:
            walls_to_check.append('left')
        if not self.lock_right:
            walls_to_check.append('right')
        
        for wall in walls_to_check:
            should_lock = False
            
            if wall == 'top' and self.y1 - self.config.lookahead_pixels < 0:
                should_lock = True
            elif wall == 'bottom' and self.y2 + self.config.lookahead_pixels >= screen_height:
                should_lock = True
            elif wall == 'left' and self.x1 - self.config.lookahead_pixels < 0:
                should_lock = True
            elif wall == 'right' and self.x2 + self.config.lookahead_pixels >= screen_width:
                should_lock = True
            
            # Check exclusion zone boundaries
            if not should_lock and self.exclusion_zone is not None:
                ex_x1, ex_y1, ex_x2, ex_y2 = self.exclusion_zone
                
                if wall == 'top':
                    # Only lock if we're below the zone and moving toward it
                    if self.y2 > ex_y1 and self.y1 - self.config.lookahead_pixels < ex_y2:
                        should_lock = True
                elif wall == 'bottom':
                    # Only lock if we're above the zone and moving toward it
                    if self.y1 < ex_y2 and self.y2 + self.config.lookahead_pixels > ex_y1:
                        should_lock = True
                elif wall == 'left':
                    # Only lock if we're to the right of the zone and moving toward it
                    if self.x2 > ex_x1 and self.x1 - self.config.lookahead_pixels < ex_x2:
                        should_lock = True
                elif wall == 'right':
                    # Only lock if we're to the left of the zone and moving toward it
                    if self.x1 < ex_x2 and self.x2 + self.config.lookahead_pixels > ex_x1:
                        should_lock = True
            
            if not should_lock:
                current_pixels = self._get_wall_pixels(wall)
                next_pixels = self._get_next_wall_pixels(wall, self.config.lookahead_pixels)
                
                if next_pixels is None or current_pixels is None:
                    continue
                
                color_changed = False
                
                color_changed = self.compare_func(wall, current_pixels, next_pixels, sample_rate)
                
                if color_changed:
                    should_lock = True
            
            if should_lock:
                if wall == 'top':
                    self.lock_top = True
                elif wall == 'bottom':
                    self.lock_bottom = True
                elif wall == 'left':
                    self.lock_left = True
                elif wall == 'right':
                    self.lock_right = True
        
        if (self.lock_left and self.lock_right) or (self.lock_top and self.lock_bottom):
            self.growth_complete = True
        elif sum([self.lock_left, self.lock_right, self.lock_top, self.lock_bottom]) >= 3:
            self.growth_complete = True


def grow_seeds(num_seeds: int, num_keep: int, screen_pixels: np.ndarray, 
               lookahead_pixels: int = 1, wall_thickness: int = 1,
               color_mode: str = 'corners', jitter: int = 0,
               growth_pixels: int = 1, pixel_sample_rate: int = 1,
               no_overlap: bool = False, exclusion_zone: tuple = None):
    
    screen_height, screen_width = screen_pixels.shape[:2]
    
    # Create comparison function based on color mode
    if color_mode == 'average':
        def compare_func(wall, current_pixels, next_pixels, sample_rate):
            return compare_avg_color_numba(current_pixels, next_pixels, sample_rate)
    else:
        def compare_func(wall, current_pixels, next_pixels, sample_rate):
            if wall == 'top' or wall == 'bottom':
                return compare_corner_horizontal_numba(current_pixels, next_pixels, sample_rate)
            else:
                return compare_corner_vertical_numba(current_pixels, next_pixels, sample_rate)
    
    config = Config(
        lookahead_pixels=lookahead_pixels,
        wall_thickness=wall_thickness,
        color_mode=color_mode,
        jitter=jitter,
        growth_pixels=growth_pixels,
        pixel_sample_rate=pixel_sample_rate
    )
    
    grid_cols = int(np.ceil(np.sqrt(num_seeds)))
    grid_rows = int(np.ceil(num_seeds / grid_cols))
    
    col_spacing = screen_width / (grid_cols + 1)
    row_spacing = screen_height / (grid_rows + 1)
    
    seeds = []
    seed_idx = 0
    for row in range(grid_rows):
        for col in range(grid_cols):
            if seed_idx >= num_seeds:
                break
            
            center_x = int((col + 1) * col_spacing)
            center_y = int((row + 1) * row_spacing)
            
            if jitter > 0:
                import random
                center_x += random.randint(-jitter, jitter)
                center_y += random.randint(-jitter, jitter)
                center_x = max(0, min(screen_width, center_x))
                center_y = max(0, min(screen_height, center_y))
            
            seed = Seed(center_x, center_y, config, screen_pixels, seed_idx, compare_func, exclusion_zone=exclusion_zone)
            seeds.append(seed)
            seed_idx += 1
    
    active_seeds = seeds[:]
    
    while active_seeds:
        for seed in active_seeds:
            seed.check_and_lock_walls(pixel_sample_rate)
        
        for seed in active_seeds:
            seed.grow()
        
        active_seeds = [s for s in active_seeds if not s.growth_complete]

    sorted_seeds = sorted(enumerate(seeds), key=lambda x: x[1].get_area(), reverse=True)
    
    if no_overlap:
        def rectangles_overlap(rect1, rect2):
            x1_a, y1_a, x2_a, y2_a = rect1
            x1_b, y1_b, x2_b, y2_b = rect2
            return not (x2_a < x1_b or x2_b < x1_a or y2_a < y1_b or y2_b < y1_a)
        
        top_seeds = []
        for original_idx, seed in sorted_seeds:
            seed_rect = seed.get_coords()
            overlaps = False
            for _, selected_seed in top_seeds:
                if rectangles_overlap(seed_rect, selected_seed.get_coords()):
                    overlaps = True
                    break
            
            if not overlaps:
                top_seeds.append((original_idx, seed))
                if len(top_seeds) >= num_keep:
                    break
    else:
        top_seeds = sorted_seeds[:num_keep]
    
    return [(seed.get_coords(), seed.get_area()) for _, seed in top_seeds]
