import sys
import json
import os
from pathlib import Path
import shutil
import random
import threading
import hashlib
import time
import numpy as np
import bettercam
from seed_growth_core import grow_seeds

# Suppress Qt DPI warnings on Windows and configure WebEngine
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""
os.environ["QT_DEBUG_PLUGINS"] = "0"

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QApplication, QProgressBar, QDialog, QLabel, QMessageBox
)
import tkinter as tk
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QSize, QUrl, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QRegion, QPixmap, QPainter, QPen, QColor


def create_app_icon():
    """Create a simple blue hollow circle icon"""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw hollow blue circle
    pen = QPen(QColor(100, 150, 255), 6)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(6, 6, size - 12, size - 12)
    painter.end()
    
    return QIcon(pixmap)


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


def load_monitoring_config(config_path='config.json'):
    """Load configuration from JSON file"""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


class SelectAllLineEdit(QLineEdit):
    """QLineEdit that selects all text on focus or click"""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()


class ConfigDialog(QDialog):
    """Modern config dialog for cache and cookie management"""
    def __init__(self, parent, cache_path, storage_path):
        super().__init__(parent)
        self.cache_path = cache_path
        self.storage_path = storage_path
        self.setWindowTitle("Settings")
        self.setWindowIcon(create_app_icon())
        self.setFixedSize(400, 250)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                border-radius: 8px;
            }
            QLabel {
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial;
                font-size: 13px;
            }
            QLabel#title {
                font-size: 16px;
                font-weight: bold;
                color: #89b4fa;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("⚙️  Settings")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # Divider
        divider = QLabel("─" * 35)
        divider.setStyleSheet("color: #45475a; margin: 5px 0px;")
        layout.addWidget(divider)
        
        # Cache section
        cache_label = QLabel("Cache Management")
        cache_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        layout.addWidget(cache_label)
        
        self.clear_cache_btn = QPushButton("🗑️  Clear Browser Cache")
        self.clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #6c7086;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
        """)
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        layout.addWidget(self.clear_cache_btn)
        
        # Cookies section
        cookies_label = QLabel("Cookie Management")
        cookies_label.setStyleSheet("color: #a6e3a1; font-weight: bold; margin-top: 8px;")
        layout.addWidget(cookies_label)
        
        self.clear_cookies_btn = QPushButton("🍪 Clear Cookies")
        self.clear_cookies_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #6c7086;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
        """)
        self.clear_cookies_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cookies_btn.clicked.connect(self.clear_cookies)
        layout.addWidget(self.clear_cookies_btn)
        
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Center dialog on parent
        if parent:
            parent_geo = parent.geometry()
            dialog_x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            dialog_y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(dialog_x, dialog_y)
    
    def clear_cache(self):
        """Clear browser cache"""
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear the browser cache?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.exists(self.cache_path):
                shutil.rmtree(self.cache_path)
                os.makedirs(self.cache_path, exist_ok=True)
            QMessageBox.information(self, "Success", "✓ Browser cache cleared successfully!")
            self.clear_cache_btn.setText("✓ Cache cleared!")
            self.clear_cache_btn.setEnabled(False)
            QTimer.singleShot(2000, lambda: self.reset_cache_button())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear cache: {str(e)}")
    
    def clear_cookies(self):
        """Clear cookies"""
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear cookies?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.exists(self.storage_path):
                shutil.rmtree(self.storage_path)
                os.makedirs(self.storage_path, exist_ok=True)
            QMessageBox.information(self, "Success", "✓ Cookies cleared successfully!")
            self.clear_cookies_btn.setText("✓ Cookies cleared!")
            self.clear_cookies_btn.setEnabled(False)
            QTimer.singleShot(2000, lambda: self.reset_cookies_button())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear cookies: {str(e)}")
    
    def reset_cache_button(self):
        """Reset cache button after clearing"""
        self.clear_cache_btn.setText("🗑️  Clear Browser Cache")
        self.clear_cache_btn.setEnabled(True)
    
    def reset_cookies_button(self):
        """Reset cookies button after clearing"""
        self.clear_cookies_btn.setText("🍪 Clear Cookies")
        self.clear_cookies_btn.setEnabled(True)


class ScreenMonitorSignals(QObject):
    """Qt signals for thread-safe communication"""
    rectangle_detected = pyqtSignal(int, int, int, int, int)  # x1, y1, x2, y2, area


class PIPVideoBrowser(QMainWindow):
    def __init__(self, start_url=None, test_movement=False):
        super().__init__()
        self.is_maximized_mode = False
        self.is_web_fullscreen = False
        self.test_movement = test_movement
        self.start_url = start_url or "https://youtube.com"
        self.config_file = Path.home() / ".pip_video_browser" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Screen monitoring setup
        self.monitoring_enabled = False
        self.monitor_thread = None
        self.monitor_signals = ScreenMonitorSignals()
        self.monitor_signals.rectangle_detected.connect(self.on_rectangle_detected)
        self.previous_hashes = None
        self.camera = None
        self.camera_lock = threading.Lock()
        
        # Load monitoring config
        self.monitor_config = load_monitoring_config()
        self.screen_width = 0
        self.screen_height = 0
        
        # Debug overlay
        self.overlay_window = None
        self.overlay_canvas = None
        self.detected_rect = None
        
        # Create persistent web engine profile for cookies and browser data
        storage_path = str(Path.home() / ".pip_video_browser" / "web_data")
        cache_path = str(Path.home() / ".pip_video_browser" / "cache")
        
        # Create cache directories if they don't exist
        Path(storage_path).mkdir(parents=True, exist_ok=True)
        Path(cache_path).mkdir(parents=True, exist_ok=True)
        
        self.profile = QWebEngineProfile("pip_video_browser", None)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setCachePath(cache_path)
        
        # Suppress JavaScript console warnings and errors
        self.profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        self.setWindowTitle("PIP Video Browser")
        self.setWindowIcon(create_app_icon())
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        self.init_ui()
        self.load_state()
        self.setMouseTracking(True)
        self.resize_timer = QTimer()
        self.resize_timer.timeout.connect(self.update_size)
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.update_position)
        
        # Test movement timer
        if self.test_movement:
            self.test_timer = QTimer()
            self.test_timer.timeout.connect(self.random_move_and_resize)
            self.test_timer.start(2500)  # Every 2.5 seconds

    def init_ui(self):
        """Initialize the user interface"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Set rounded corners on main widget
        main_widget.setStyleSheet("""
            QWidget {
                border-radius: 12px;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create web engine first (needed by control buttons)
        self.web_view = QWebEngineView()
        page = QWebEnginePage(self.profile, self.web_view)
        
        # Enable fullscreen support for video players
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        
        # Handle fullscreen requests from web content (YouTube, Netflix, etc.)
        page.fullScreenRequested.connect(self.handle_fullscreen_request)
        
        # Inject script to suppress JavaScript console messages
        script = """
        (function() {
            // Suppress console warnings and errors related to policies and headers
            const originalWarn = console.warn;
            const originalError = console.error;
            
            console.warn = function(...args) {
                const message = args.join(' ');
                // Filter out common browser-related warnings
                if (message.includes('Permissions-Policy') || 
                    message.includes('Document-Policy') ||
                    message.includes('preload') ||
                    message.includes('link preload')) {
                    return;
                }
                originalWarn.apply(console, args);
            };
            
            console.error = function(...args) {
                const message = args.join(' ');
                // Filter out CORS and advertisement-related errors
                if (message.includes('CORS') || 
                    message.includes('doubleclick.net') ||
                    message.includes('XMLHttpRequest')) {
                    return;
                }
                originalError.apply(console, args);
            };
        })();
        """
        page.runJavaScript(script)
        
        self.web_view.setPage(page)
        
        # Compact mode button (shown in compact mode, top)
        self.maximize_btn = QPushButton("⛶")
        self.maximize_btn.setFixedWidth(30)
        self.maximize_btn.setFixedHeight(30)
        self.maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(100, 150, 255, 0.15);
            }
            QPushButton:pressed {
                background-color: rgba(80, 120, 200, 0.25);
            }
        """)
        self.maximize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.maximize_btn.clicked.connect(self.toggle_mode)
        main_layout.addWidget(self.maximize_btn)
        
        # Control bar (shown in maximized mode, top)
        self.control_bar = QWidget()
        control_layout = QHBoxLayout(self.control_bar)
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_layout.setSpacing(5)
        
        # Button styling
        button_style = """
            QPushButton {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(100, 150, 255, 0.15);
            }
            QPushButton:pressed {
                background-color: rgba(80, 120, 200, 0.25);
            }
        """
        
        self.back_btn = QPushButton("◀")
        self.back_btn.setFixedWidth(30)
        self.back_btn.setFixedHeight(30)
        self.back_btn.setStyleSheet(button_style)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.web_view.back)
        control_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("▶")
        self.forward_btn.setFixedWidth(30)
        self.forward_btn.setFixedHeight(30)
        self.forward_btn.setStyleSheet(button_style)
        self.forward_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forward_btn.clicked.connect(self.web_view.forward)
        control_layout.addWidget(self.forward_btn)
        
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.setStyleSheet(button_style)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.web_view.reload)
        control_layout.addWidget(self.refresh_btn)
        
        self.url_bar = SelectAllLineEdit()
        self.url_bar.setPlaceholderText("Enter URL...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setStyleSheet("""
            QLineEdit {
                border-radius: 8px;
                padding: 5px;
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
            }
            QLineEdit:hover {
                background-color: rgba(100, 150, 255, 0.15);
            }
            QLineEdit:focus {
                background-color: rgba(80, 120, 200, 0.25);
            }
        """)
        control_layout.addWidget(self.url_bar)
        
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.setStyleSheet(button_style)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_config_menu)
        control_layout.addWidget(self.settings_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedWidth(30)
        self.close_btn.setFixedHeight(30)
        self.close_btn.setStyleSheet(button_style)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        control_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(self.control_bar)
        
        # Add loading progress bar (shown under control bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
                margin: 0px;
                padding: 0px;
            }
            QProgressBar::chunk {
                background-color: rgba(100, 150, 255, 0.9);
            }
        """)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)
        
        # Connect web view loading signals
        self.web_view.loadStarted.connect(self.on_load_started)
        self.web_view.loadProgress.connect(self.on_load_progress)
        self.web_view.loadFinished.connect(self.on_load_finished)
        
        # Connect URL changed signal to update URL bar
        self.web_view.urlChanged.connect(self.on_url_changed)
        
        # Add web engine to layout (fills remaining space)
        main_layout.addWidget(self.web_view, 1)
        
        main_widget.setLayout(main_layout)
        self.set_compact_mode()
        
        # Load default URL
        self.web_view.setUrl(QUrl(self.start_url))

    def set_compact_mode(self):
        """Switch to compact mode (minimal UI)"""
        self.is_maximized_mode = False
        self.control_bar.hide()
        self.maximize_btn.hide()
        self.resize(640, 480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.show()
        self.apply_rounded_corners()
        
        # Start screen monitoring in compact mode (unless test_movement is enabled)
        if not self.test_movement:
            self.start_screen_monitoring()

    def set_maximized_mode(self):
        """Switch to maximized mode (full controls)"""
        self.is_maximized_mode = True
        self.control_bar.show()
        self.maximize_btn.hide()
        self.resize(900, 600)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.show()
        self.apply_rounded_corners()
        
        # Stop screen monitoring in maximized mode
        self.stop_screen_monitoring()

    def toggle_mode(self):
        """Toggle between compact and maximized modes"""
        if self.is_maximized_mode:
            self.set_compact_mode()
        else:
            self.set_maximized_mode()
        self.save_state()

    def apply_rounded_corners(self):
        """Apply rounded corners to the window with antialiasing"""
        from PyQt6.QtGui import QBitmap, QPainter
        
        # Create a bitmap mask
        mask = QBitmap(self.size())
        mask.fill(Qt.GlobalColor.white)
        
        # Draw rounded rectangle on the bitmap with antialiasing
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        painter.end()
        
        self.setMask(mask)

    def on_load_started(self):
        """Handle page load started"""
        self.progress_bar.show()
        self.progress_bar.setValue(0)

    def on_load_progress(self, progress):
        """Handle page load progress"""
        self.progress_bar.setValue(progress)

    def on_load_finished(self):
        """Handle page load finished"""
        self.progress_bar.setValue(100)
        self.progress_bar.hide()

    def navigate_to_url(self):
        """Navigate to URL from address bar"""
        url = self.url_bar.text().strip()
        if not url:
            return
        
        # Check if it looks like a URL (contains a dot or is localhost)
        if "." in url or url.lower().startswith("localhost"):
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            self.web_view.setUrl(QUrl(url))
        else:
            # Search Google for non-URL input
            search_url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
            self.web_view.setUrl(QUrl(search_url))

    def on_url_changed(self):
        """Update URL bar when the web view's URL changes"""
        self.url_bar.setText(self.web_view.url().toString())

    def open_config_menu(self):
        """Open the configuration menu dialog"""
        cache_path = str(Path.home() / ".pip_video_browser" / "cache")
        storage_path = str(Path.home() / ".pip_video_browser" / "web_data")
        config_dialog = ConfigDialog(self, cache_path, storage_path)
        config_dialog.exec()

    def set_position(self, x, y):
        """Non-blocking position change"""
        self.pending_x = x
        self.pending_y = y
        self.move_timer.start(0)

    def update_position(self):
        """Update position non-blocking"""
        if hasattr(self, 'pending_x') and hasattr(self, 'pending_y'):
            self.move(self.pending_x, self.pending_y)
            self.move_timer.stop()

    def random_move_and_resize(self):
        """Move window to random position and size (for testing) - only in compact mode"""
        # Only move when in compact mode and monitoring is not enabled
        if self.is_maximized_mode or self.monitoring_enabled:
            return
        
        # Get screen geometry
        screen = QApplication.primaryScreen().geometry()
        
        # Random size (200-800 width, 150-600 height)
        new_width = random.randint(200, 800)
        new_height = random.randint(150, 600)
        
        # Random position (ensure window stays on screen)
        max_x = screen.width() - new_width
        max_y = screen.height() - new_height
        new_x = random.randint(0, max(max_x, 0))
        new_y = random.randint(0, max(max_y, 0))
        
        # Apply new geometry
        self.setGeometry(new_x, new_y, new_width, new_height)
        self.apply_rounded_corners()
    
    def start_screen_monitoring(self):
        """Start the screen monitoring thread"""
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            return
        
        self.monitoring_enabled = True
        
        # Initialize camera if not already created
        with self.camera_lock:
            if self.camera is None:
                try:
                    self.camera = bettercam.create(output_color="BGR")
                    print("📷 Camera initialized")
                except Exception as e:
                    print(f"Failed to initialize camera: {e}")
                    return
        
        # Debug overlay disabled
        # self._create_overlay_window()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🔍 Screen monitoring started")
    
    def _create_overlay_window(self):
        """Create transparent overlay window for debug visualization"""
        if self.overlay_window is not None:
            return
        
        try:
            self.overlay_window = tk.Tk()
            self.overlay_window.attributes('-topmost', True)
            self.overlay_window.overrideredirect(True)
            self.overlay_window.attributes('-transparentcolor', 'white')
            
            # Get screen dimensions
            screen = QApplication.primaryScreen().geometry()
            self.overlay_window.geometry(f"{screen.width()}x{screen.height()}+0+0")
            
            self.overlay_canvas = tk.Canvas(self.overlay_window, bg='white', highlightthickness=0)
            self.overlay_canvas.pack(fill=tk.BOTH, expand=True)
            
            print("🖼️  Debug overlay created")
        except Exception as e:
            print(f"Failed to create overlay: {e}")
    
    def _update_overlay(self):
        """Update the debug overlay to show detected rectangle"""
        if self.overlay_canvas is None or self.detected_rect is None:
            return
        
        try:
            self.overlay_canvas.delete("all")
            x1, y1, x2, y2 = self.detected_rect
            
            # Draw detected rectangle in red (physical pixels)
            self.overlay_canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=3, fill='')
            
            # Get DPI scaling to convert Qt logical pixels back to physical
            screen = QApplication.primaryScreen()
            dpi_scale = screen.devicePixelRatio()
            
            # Draw PIP window position in blue - convert logical to physical pixels
            frame_geo = self.frameGeometry()
            pip_logical_x = frame_geo.x()
            pip_logical_y = frame_geo.y()
            pip_logical_w = frame_geo.width()
            pip_logical_h = frame_geo.height()
            
            # Convert to physical pixels for overlay
            pip_x = int(pip_logical_x * dpi_scale)
            pip_y = int(pip_logical_y * dpi_scale)
            pip_w = int(pip_logical_w * dpi_scale)
            pip_h = int(pip_logical_h * dpi_scale)
            
            print(f"🔵 Blue rect (PIP physical): ({pip_x}, {pip_y}) to ({pip_x + pip_w}, {pip_y + pip_h})")
            print(f"🔴 Red rect (detected physical): ({x1}, {y1}) to ({x2}, {y2})")
            
            self.overlay_canvas.create_rectangle(
                pip_x, pip_y, 
                pip_x + pip_w, pip_y + pip_h,
                outline='blue', width=2, fill=''
            )
            
            self.overlay_window.update()
        except Exception as e:
            print(f"Error updating overlay: {e}")
    
    def stop_screen_monitoring(self):
        """Stop the screen monitoring thread"""
        self.monitoring_enabled = False
        
        # Destroy overlay window
        if self.overlay_window is not None:
            try:
                self.overlay_window.destroy()
            except:
                pass
            self.overlay_window = None
            self.overlay_canvas = None
        
        print("🛑 Screen monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        try:
            # Initial capture to get screen dimensions
            with self.camera_lock:
                if self.camera is None:
                    print("Camera not initialized")
                    return
                screen_capture = self.camera.grab()
            
            if screen_capture is None:
                print("Failed to grab initial screen capture")
                return
            
            screen_pixels = np.array(screen_capture)
            screen_pixels = screen_pixels[:, :, [2, 1, 0]]
            
            self.screen_height, self.screen_width = screen_pixels.shape[:2]
            
            # Perform initial seed growth search
            print("🌱 Performing initial seed growth search...")
            self._search_and_emit(screen_pixels)
            
            # Initialize block hashes
            block_size = self.monitor_config.get('block_size', 100)
            self.previous_hashes = get_all_block_hashes(screen_pixels, block_size)
            
            update_rate = self.monitor_config.get('update_rate', 0.1)
            change_threshold = self.monitor_config.get('change_threshold', 30.0)
            iteration = 0
            
            while self.monitoring_enabled:
                time.sleep(update_rate)
                iteration += 1
                
                with self.camera_lock:
                    if self.camera is None:
                        break
                    screen_capture = self.camera.grab()
                
                if screen_capture is None:
                    continue
                
                try:
                    screen_pixels = np.array(screen_capture)
                    if screen_pixels.ndim < 3:
                        continue
                    screen_pixels = screen_pixels[:, :, [2, 1, 0]]
                except (IndexError, ValueError):
                    continue
                
                current_hashes = get_all_block_hashes(screen_pixels, block_size)
                change_percentage = calculate_change_percentage(self.previous_hashes, current_hashes)
                
                if change_percentage > change_threshold:
                    print(f"[{iteration:03d}] {change_percentage:5.1f}% blocks changed - searching for new rectangle")
                    self._search_and_emit(screen_pixels)
                
                self.previous_hashes = current_hashes
        
        except Exception as e:
            print(f"Monitor error: {e}")
            import traceback
            traceback.print_exc()
    
    def _search_and_emit(self, screen_pixels):
        """Search for rectangle and emit signal"""
        try:
            # Get exclusion zone from config (currently 0% in config.json)
            exclude_center_width = self.monitor_config.get('exclude_center_width', 0)
            exclude_center_height = self.monitor_config.get('exclude_center_height', 0)
            
            exclude_width = int(self.screen_width * exclude_center_width / 100)
            exclude_height = int(self.screen_height * exclude_center_height / 100)
            
            exclude_x1 = (self.screen_width - exclude_width) // 2
            exclude_y1 = (self.screen_height - exclude_height) // 2
            exclude_x2 = exclude_x1 + exclude_width
            exclude_y2 = exclude_y1 + exclude_height
            
            exclusion_zone = (exclude_x1, exclude_y1, exclude_x2, exclude_y2) if exclude_width > 0 and exclude_height > 0 else None
            
            results = grow_seeds(
                num_seeds=self.monitor_config.get('seeds', 100),
                num_keep=1,
                screen_pixels=screen_pixels,
                lookahead_pixels=self.monitor_config.get('lookahead_pixels', 5),
                wall_thickness=self.monitor_config.get('wall_thickness', 5),
                color_mode=self.monitor_config.get('color_mode', 'average'),
                jitter=self.monitor_config.get('jitter', 25),
                growth_pixels=self.monitor_config.get('growth_pixels', 1),
                pixel_sample_rate=self.monitor_config.get('pixel_sample_rate', 1),
                no_overlap=self.monitor_config.get('no_overlap', True),
                exclusion_zone=exclusion_zone
            )
            
            if results:
                coords, area = results[0]
                x1, y1, x2, y2 = coords
                self.monitor_signals.rectangle_detected.emit(x1, y1, x2, y2, area)
                print(f"  → Rectangle detected: ({x1}, {y1}, {x2}, {y2}) - {area} px²")
        
        except Exception as e:
            print(f"Error in seed growth: {e}")
    
    def on_rectangle_detected(self, x1, y1, x2, y2, area):
        """Handle detected rectangle - position PIP window inside it"""
        # Store detected rectangle for overlay
        self.detected_rect = (x1, y1, x2, y2)
        
        if not self.is_maximized_mode:  # Only reposition in compact mode
            # Get DPI scaling factor
            screen = QApplication.primaryScreen()
            dpi_scale = screen.devicePixelRatio()
            
            print(f"🖥️  DPI Scale Factor: {dpi_scale}")
            
            # Convert physical pixels to logical pixels
            logical_x1 = int(x1 / dpi_scale)
            logical_y1 = int(y1 / dpi_scale)
            logical_x2 = int(x2 / dpi_scale)
            logical_y2 = int(y2 / dpi_scale)
            
            logical_width = logical_x2 - logical_x1
            logical_height = logical_y2 - logical_y1
            
            print(f"📐 Detected rect (physical): ({x1}, {y1}) to ({x2}, {y2})")
            print(f"📐 Detected rect (logical): ({logical_x1}, {logical_y1}) to ({logical_x2}, {logical_y2})")
            print(f"📍 Positioning PIP using logical coordinates")
            
            # Apply the logical coordinates to Qt window
            self.setGeometry(logical_x1, logical_y1, logical_width, logical_height)
            self.apply_rounded_corners()
            
            # Debug overlay disabled
            # QTimer.singleShot(0, self._update_overlay)

    def set_size(self, width, height):
        """Non-blocking resize"""
        self.pending_width = width
        self.pending_height = height
        self.resize_timer.start(0)

    def update_size(self):
        """Update size non-blocking"""
        if hasattr(self, 'pending_width') and hasattr(self, 'pending_height'):
            self.resize(self.pending_width, self.pending_height)
            self.resize_timer.stop()

    def save_state(self):
        """Persist window state to disk"""
        state = {
            "x": self.x(),
            "y": self.y(),
            "width": self.width(),
            "height": self.height(),
            "is_maximized": self.is_maximized_mode,
            "url": self.url_bar.text() or self.start_url
        }
        with open(self.config_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self):
        """Restore window state from disk"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    state = json.load(f)
                self.move(state.get("x", 100), state.get("y", 100))
                self.resize(state.get("width", 640), state.get("height", 480))
                
                if state.get("is_maximized", False):
                    self.set_maximized_mode()
                else:
                    self.set_compact_mode()
                    
                self.web_view.setUrl(QUrl(self.start_url))
            except Exception as e:
                print(f"Error loading state: {e}")
        else:
            self.move(100, 100)

    def handle_fullscreen_request(self, request):
        """Handle fullscreen requests from web content (YouTube, Netflix, etc.)"""
        if request.toggleOn():
            # Entering fullscreen - accept the request and switch to compact mode
            request.accept()
            self.is_web_fullscreen = True
            
            # Switch to compact mode (minimal UI)
            self.set_compact_mode()
            
        else:
            # Exiting fullscreen - accept the request and switch to maximized mode
            request.accept()
            self.is_web_fullscreen = False
            
            # Switch to maximized mode (show controls)
            self.set_maximized_mode()

    def closeEvent(self, event):
        """Handle window close event"""
        self.save_state()
        
        # Stop screen monitoring
        self.stop_screen_monitoring()
        
        # Release camera
        with self.camera_lock:
            if self.camera:
                try:
                    self.camera.release()
                except:
                    pass
                self.camera = None
        
        # Properly clean up web page before closing
        if hasattr(self, 'web_view') and self.web_view.page():
            self.web_view.setPage(None)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(create_app_icon())
    
    start_url = None
    test_movement = False
    
    # Parse command-line arguments
    for arg in sys.argv[1:]:
        if arg == "--test-movement":
            test_movement = True
        elif not arg.startswith("--"):
            start_url = arg
    
    browser = PIPVideoBrowser(start_url, test_movement)
    browser.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
