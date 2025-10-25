import sys
import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QApplication
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QSize, QUrl
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QRegion


class PIPVideoBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_maximized_mode = False
        self.config_file = Path.home() / ".pip_video_browser" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create persistent web engine profile for cookies and browser data
        storage_path = str(Path.home() / ".pip_video_browser" / "web_data")
        self.profile = QWebEngineProfile("pip_video_browser", None)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setCachePath(str(Path.home() / ".pip_video_browser" / "cache"))
        
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
        self.web_view.setPage(page)
        
        # Compact mode button (shown in compact mode, top)
        self.maximize_btn = QPushButton("⛶")
        self.maximize_btn.setMaximumWidth(40)
        self.maximize_btn.setMaximumHeight(40)
        self.maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(100, 150, 255, 0.8);
            }
            QPushButton:pressed {
                background-color: rgba(80, 120, 200, 0.9);
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
                background-color: rgba(100, 150, 255, 0.8);
            }
            QPushButton:pressed {
                background-color: rgba(80, 120, 200, 0.9);
            }
        """
        
        self.back_btn = QPushButton("◀")
        self.back_btn.setMaximumWidth(35)
        self.back_btn.setStyleSheet(button_style)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.web_view.back)
        control_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("▶")
        self.forward_btn.setMaximumWidth(35)
        self.forward_btn.setStyleSheet(button_style)
        self.forward_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forward_btn.clicked.connect(self.web_view.forward)
        control_layout.addWidget(self.forward_btn)
        
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setMaximumWidth(35)
        self.refresh_btn.setStyleSheet(button_style)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.web_view.reload)
        control_layout.addWidget(self.refresh_btn)
        
        self.url_bar = QLineEdit()
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
                background-color: rgba(100, 150, 255, 0.8);
            }
            QLineEdit:focus {
                background-color: rgba(80, 120, 200, 0.9);
            }
        """)
        control_layout.addWidget(self.url_bar)
        
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setMaximumWidth(35)
        self.minimize_btn.setStyleSheet(button_style)
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.toggle_mode)
        control_layout.addWidget(self.minimize_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setMaximumWidth(35)
        self.close_btn.setStyleSheet(button_style)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        control_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(self.control_bar)
        
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
        event.accept()


def main():
    app = QApplication(sys.argv)
    browser = PIPVideoBrowser()
    browser.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
