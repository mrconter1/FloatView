# FloatView - Intelligent PIP Video Browser

An always-on-top video browser that automatically positions itself in unused screen areas. It monitors your screen for changes and finds the largest calm, non-changing rectangular region to occupy - like empty desktop space, unused document windows, or browser backgrounds. When you move windows or your layout changes significantly, it automatically repositions itself to stay out of your way while remaining visible.

![Demo](demo.gif)

## How It Works

### 1. PIP Browser
A frameless PyQt6 web browser with two modes:
- **Compact mode**: Just video, no controls (always-on-top)
- **Maximized mode**: Full browser controls (navigation, URL bar, settings)

Press `⛶` button or use browser fullscreen to toggle between modes.

### 2. Seed Growth Rectangle Detection
Plants seeds across the screen that grow until hitting color boundaries, finding the largest uniform rectangular area:
- Seeds expand maintaining 16:9 aspect ratio
- Growth stops at edges where colors change (uses average or corner sampling)
- Returns largest non-overlapping rectangle(s)
- Fast with Numba JIT compilation

### 3. Adaptive Positioning Loop
When in compact mode:
1. Capture screen every 0.1s and hash into blocks
2. Calculate % of blocks that changed
3. If change > 30% threshold → run seed growth
4. Find largest static rectangular area
5. Position PIP window to fill that rectangle
6. Adjust web content zoom to fit
7. Repeat

The browser automatically finds "quiet" screen space and stays out of active work areas.

## Installation

```powershell
pip install -r requirements.txt
```

## Usage

Basic:
```powershell
python pip_video_browser.py
```

With URL:
```powershell
python pip_video_browser.py https://youtube.com/watch?v=VIDEO_ID
```

Test movement (disables monitoring):
```powershell
python pip_video_browser.py --test-movement
```

## Configuration

Edit `config.json` to tune detection:

```json
{
  "seeds": 100,              // Number of growth seeds
  "block_size": 100,         // Block size for change detection
  "update_rate": 0.1,        // Check interval (seconds)
  "change_threshold": 30,    // % change to trigger repositioning
  "lookahead_pixels": 5,     // Edge detection sensitivity
  "wall_thickness": 5,       // Edge sampling thickness
  "color_mode": "average",   // "average" or "corners"
  "growth_pixels": 1,        // Growth speed per iteration
  "no_overlap": true         // Only keep non-overlapping rectangles
}
```

## Components

- `pip_video_browser.py` - Main PIP browser with monitoring integration
- `seed_growth_core.py` - Rectangle detection algorithm
- `adaptive_block_monitor.py` - Standalone monitoring tool (for testing)
- `config.json` - Detection parameters

## Controls

- **ESC** (in browser fullscreen) - Exit fullscreen, show controls
- **Browser fullscreen button** - Enter fullscreen, hide controls
- **⛶ button** - Toggle between compact/maximized modes manually
- **Settings ⚙️** - Clear cache/cookies

## Notes

- Automatically handles DPI scaling
- Web content scales to fit window size
- Camera resource persists for performance
- Only monitors in compact mode to save CPU

