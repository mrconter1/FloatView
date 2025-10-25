import sys
import json
import os
from pathlib import Path
import shutil

# Suppress Qt DPI warnings on Windows and configure WebEngine
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""
os.environ["QT_DEBUG_PLUGINS"] = "0"

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QApplication, QProgressBar, QDialog, QLabel, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QSize, QUrl
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QRegion


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


class PIPVideoBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_maximized_mode = False
        self.config_file = Path.home() / ".pip_video_browser" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
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
        
        self.minimize_btn = QPushButton("↓")
        self.minimize_btn.setFixedWidth(30)
        self.minimize_btn.setFixedHeight(30)
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 150, 0, 0.7);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 180, 50, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(255, 100, 0, 0.9);
            }
        """)
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.toggle_mode)
        control_layout.addWidget(self.minimize_btn)
        
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
        self.web_view.setUrl(QUrl("https://youtube.com"))

    def set_compact_mode(self):
        """Switch to compact mode (minimal UI)"""
        self.is_maximized_mode = False
        self.control_bar.hide()
        self.maximize_btn.show()
        self.resize(640, 480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.show()
        self.apply_rounded_corners()

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
            "url": self.url_bar.text() or "https://youtube.com"
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
                    
                self.web_view.setUrl(QUrl("https://youtube.com"))
            except Exception as e:
                print(f"Error loading state: {e}")
        else:
            self.move(100, 100)

    def closeEvent(self, event):
        """Handle window close event"""
        self.save_state()
        # Properly clean up web page before closing
        if hasattr(self, 'web_view') and self.web_view.page():
            self.web_view.setPage(None)
        event.accept()


def main():
    app = QApplication(sys.argv)
    browser = PIPVideoBrowser()
    browser.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
