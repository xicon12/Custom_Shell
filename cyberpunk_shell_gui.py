import sys
import os
import platform
import threading
import webbrowser
import random
import subprocess
import getpass
import time
import json
import urllib.request
import urllib.error
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFrame, QGraphicsOpacityEffect, QDialog,
                             QFontComboBox, QSpinBox, QColorDialog, QFormLayout,
                             QComboBox, QFileDialog, QSplitter, QSizePolicy, QSizeGrip)
from PyQt6.QtCore import Qt, QProcess, QTimer, QPoint, QSize, pyqtSignal, QRect, QThread
from PyQt6.QtGui import QColor, QFont, QPixmap, QCursor, QPalette, QBrush, QGuiApplication, QPainter
import markdown
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # Optional dependency

class AIChatWidget(QWidget):
    def __init__(self, parent=None, current_model="gemini-2.5-flash-lite"):
        super().__init__(parent)
        self.current_model = current_model
        # ... (rest of init)

    # ... (skipping methods until append_message)

    def append_message(self, sender, text, color):
        # Parse Markdown for AI responses
        formatted_text = text
        if sender not in ["YOU", "SYSTEM"]:
            try:
                formatted_text = markdown.markdown(text, extensions=['fenced_code', 'codehilite'])
            except Exception:
                pass # Fallback to plain text
        
        # Replace newlines with <br> for plain text if not HTML
        if formatted_text == text:
             formatted_text = text.replace("\n", "<br>")
             
        # Format bold for sender
        html_msg = f"<span style='color: {color}; font-weight: bold;'>[{sender}]</span> <span style='color: #dddddd;'>{formatted_text}</span>"
        self.chat_history.append(html_msg)
        self.chat_history.append("") # Spacing
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)
        sound_manager.play_typing()

# Try psutil for accurate memory stats, else standard lib fallbacks
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Sound imports
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Configuration
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
DEFAULT_BG_PATH = "cyberpunk_bg.png"
SHELL_CMD_LINUX = "./advsh"
SHELL_CMD_MOCK = "python mock_advsh.py" 

# Default Colors
NEON_CYAN = "#00fff0"
NEON_MAGENTA = "#ff00ff"
NEON_PURPLE = "#bc13fe"
NEON_GREEN = "#39ff14"
TERM_BG_COLOR = "rgba(10, 10, 16, 150)" 
INPUT_BG_COLOR = "rgba(20, 20, 30, 180)"

# Gemini API Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

class SoundManager:
    """Optimized Audio FX with themes."""
    THEMES = {
        "High Tech": {"type": (-1,), "enter": "SystemAsterisk", "startup": "SystemExclamation"},
        "Retro": {"type": (1000, 50), "enter": (500, 100), "startup": (300, 300)}, # Freq/Dur for beep
        "Silent": {"type": None, "enter": None, "startup": None}
    }

    def __init__(self):
        self.current_theme = "High Tech"
    
    def set_theme(self, theme_name):
        if theme_name in self.THEMES:
            self.current_theme = theme_name

    def play_beep_thread(self, freq, dur=None):
        if not HAS_WINSOUND: return
        if dur is None:
            winsound.MessageBeep(freq)
        else:
             winsound.Beep(freq, dur)

    def play_typing(self):
        cfg = self.THEMES[self.current_theme]["type"]
        if not cfg or not HAS_WINSOUND: return
        
        if len(cfg) == 1:
            winsound.MessageBeep(cfg[0])
        else:
            threading.Thread(target=winsound.Beep, args=cfg, daemon=True).start()

    def play_enter(self):
        cfg = self.THEMES[self.current_theme]["enter"]
        if not cfg or not HAS_WINSOUND: return
        
        if isinstance(cfg, str):
            winsound.PlaySound(cfg, winsound.SND_ASYNC | winsound.SND_ALIAS)
        else:
            threading.Thread(target=winsound.Beep, args=cfg, daemon=True).start()

    def play_startup(self):
        cfg = self.THEMES[self.current_theme]["startup"]
        if not cfg or not HAS_WINSOUND: return

        if isinstance(cfg, str):
            winsound.PlaySound(cfg, winsound.SND_ASYNC | winsound.SND_ALIAS)
        else:
             threading.Thread(target=winsound.Beep, args=cfg, daemon=True).start()

class SnakeGameDialog(QDialog):
    """Classic Snake Game."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SNAKE PROTOCOL")
        self.resize(600, 400)
        self.setStyleSheet(f"background-color: #101015; border: 2px solid {NEON_MAGENTA}; color: {NEON_MAGENTA}; font-family: 'Consolas'; font-size: 14px;")
        
        self.layout = QVBoxLayout(self)
        self.val_label = QLabel("SCORE: 0")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.val_label)
        
        self.game_area = QLabel()
        self.game_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_area.setStyleSheet("font-size: 16px; font-weight: bold; letter-spacing: 3px; line-height: 16px;")
        self.layout.addWidget(self.game_area)
        
        self.info_label = QLabel("ARROWS: MOVE | ESC: EXIT")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.info_label)
        
        # Logic
        self.cols = 40
        self.rows = 20
        self.snake = [(10, 10)] # Head is 0
        self.direction = (1, 0) # Right
        self.food = self.spawn_food()
        self.score = 0
        self.game_over = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_tick)
        self.timer.start(100) # 100ms

    def spawn_food(self):
        while True:
            x = random.randint(0, self.cols-1)
            y = random.randint(0, self.rows-1)
            if (x,y) not in self.snake:
                return (x,y)

    def game_tick(self):
        if self.game_over: return
        
        head = self.snake[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        
        # Collision Check
        if (new_head[0] < 0 or new_head[0] >= self.cols or 
            new_head[1] < 0 or new_head[1] >= self.rows or 
            new_head in self.snake):
            self.game_over = True
            self.game_area.setText(f"\n\nGAME OVER\nFINAL SCORE: {self.score}")
            return
            
        self.snake.insert(0, new_head)
        
        if new_head == self.food:
            self.score += 1
            self.val_label.setText(f"SCORE: {self.score}")
            self.food = self.spawn_food()
        else:
            self.snake.pop()
            
        self.render()

    def render(self):
        # 2D Grid
        grid = [["." for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Place Food
        grid[self.food[1]][self.food[0]] = "@"
        
        # Place Snake
        for i, segment in enumerate(self.snake):
            char = "O" if i == 0 else "o"
            grid[segment[1]][segment[0]] = char
            
        render_text = "\n".join(["".join(row) for row in grid])
        self.game_area.setText(render_text)

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self.close()
            return
            
        new_dir = None
        if k == Qt.Key.Key_Left and self.direction != (1,0): new_dir = (-1,0)
        elif k == Qt.Key.Key_Right and self.direction != (-1,0): new_dir = (1,0)
        elif k == Qt.Key.Key_Up and self.direction != (0,1): new_dir = (0,-1)
        elif k == Qt.Key.Key_Down and self.direction != (0,-1): new_dir = (0,1)
        
        if new_dir:
            self.direction = new_dir

class CustomCommandManager:
    """Handles special user commands directly in the GUI."""
    
    def handle_command(self, cmd_str, shell_window):
        """Returns True if command was handled, False if it should go to shell."""
        cmd = cmd_str.lower().strip()
        
        if cmd == "greet":
            user = getpass.getuser()
            self.print_response(shell_window, f"Hello, {user}! Welcome Back.")
            return True
            
        elif cmd == "weather":
            self.print_response(shell_window, "Opening weather for Pakistan in browser...")
            webbrowser.open("https://www.google.com/search?q=weather+pakistan")
            return True
        elif cmd == "funny":
            jokes = ["Why do programmers prefer dark mode? Light attracts bugs.", "I ate a clock yesterday. It was time consuming."]
            self.print_response(shell_window, random.choice(jokes))
            return True
        elif cmd == "motivation":
            quotes = ["Do it now.", "Believe you can."]
            self.print_response(shell_window, random.choice(quotes))
            return True
        elif cmd == "tip":
            self.print_response(shell_window, "Use 'ls -la' to see hidden files.")
            return True
        elif cmd == "tech related":
            webbrowser.open("https://techcrunch.com/")
            self.print_response(shell_window, "Opening Tech News...")
            return True
            
        # MODIFIED: Open External Link
        elif cmd == "linux guide":
            self.print_response(shell_window, "Opening Linux Command Guide (GeeksForGeeks)...")
            webbrowser.open("https://www.geeksforgeeks.org/linux-commands/") # Better guide link
            return True
            
        elif cmd == "screenshot":
            self.take_screenshot(shell_window)
            return True
        elif cmd == "calculator":
            self.print_response(shell_window, "Launching Calculator...")
            if platform.system() == "Windows":
                 try: subprocess.Popen("calc.exe")
                 except: pass # handled
            return True
        elif cmd == "save error":
            if shell_window.last_error:
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                if not os.path.exists(desktop): desktop = os.getcwd()
                path = os.path.join(desktop, "error.log")
                with open(path, "w") as f:
                    f.write(shell_window.last_error)
                self.print_response(shell_window, f"Error saved to: {path}")
            else:
                self.print_response(shell_window, "No errors recorded yet.")
            return True
            
        elif cmd == "game":
            self.print_response(shell_window, "Launching Snake Protocol...")
            game = SnakeGameDialog(shell_window)
            game.exec()
            return True
            
        elif cmd == "fact":
            facts = [
                "Honey never spoils.",
                "Octopuses have three hearts.",
                "Bananas are berries, but strawberries aren't.",
                "The Eiffel Tower can be 15 cm taller during the summer.",
                "A group of flamingos is called a 'flamboyance'.",
                "Bees sometimes sting other bees.",
                "The heart of a shrimp is located in its head."
            ]
            self.print_response(shell_window, f"FUN FACT: {random.choice(facts)}")
            return True
            
        elif cmd.startswith("website "):
            # Parse URL
            parts = cmd_str.split(" ", 1)
            if len(parts) > 1:
                url = parts[1].strip()
                if not url.startswith("http"):
                    url = "https://" + url
                self.print_response(shell_window, f"Opening {url}...")
                webbrowser.open(url)
            else:
                self.print_response(shell_window, "Usage: website <url>")
            return True

        return False

    def print_response(self, shell_window, text):
        shell_window.terminal.append(f"<span style='color: {NEON_GREEN};'>[SYSTEM]</span> <span style='color: white;'>{text}</span>")
        cursor = shell_window.terminal.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        shell_window.terminal.setTextCursor(cursor)

    def take_screenshot(self, shell_window):
        screen = QGuiApplication.primaryScreen()
        if not screen: return
        pixmap = shell_window.terminal.grab()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop): desktop = os.getcwd()
        path = os.path.join(desktop, f"screenshot_{random.randint(1000,9999)}.png")
        pixmap.save(path, "png")
        self.print_response(shell_window, f"Screenshot saved to: {path}")

sound_manager = SoundManager()
cmd_manager = CustomCommandManager()

class SettingsDialog(QDialog):
    settings_applied = pyqtSignal(QFont, str, int, str, str, str, str) # Added str for model
    def __init__(self, current_font, current_color, current_size, current_bg, current_sound, current_border, current_model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SYSTEM CONFIG // SETTINGS")
        self.resize(450, 500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #050510; border: 2px solid {NEON_CYAN}; }}
            QLabel {{ color: {NEON_CYAN}; font-family: 'Consolas'; font-weight: bold; }}
            QComboBox, QSpinBox, QLineEdit {{ background-color: #101020; color: white; border: 1px solid {NEON_PURPLE}; padding: 5px; }}
        """)
        layout = QFormLayout(self)
        
        # Model Selection
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gemini-2.5-flash-lite", 
            "gemini-2.0-flash"
        ])
        self.model_combo.setCurrentText(current_model)
        layout.addRow("AI MODEL:", self.model_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(current_font)
        layout.addRow("FONT_FAMILY:", self.font_combo)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 48)
        self.size_spin.setValue(current_size)
        layout.addRow("TXT_SIZE:", self.size_spin)
        self.color_btn = GlowingButton(current_color, current_color)
        self.selected_color = current_color
        self.color_btn.clicked.connect(self.choose_text_color)
        layout.addRow("TEXT_COLOR:", self.color_btn)
        self.selected_border = current_border
        self.border_btn = GlowingButton(current_border, current_border)
        self.border_btn.clicked.connect(self.choose_border_color)
        layout.addRow("BORDER_COLOR:", self.border_btn)
        self.bg_path = current_bg
        self.bg_btn = GlowingButton("BROWSE...", NEON_MAGENTA)
        self.bg_btn.clicked.connect(self.choose_bg)
        self.bg_label = QLabel(os.path.basename(current_bg))
        self.bg_label.setStyleSheet("color: gray;")
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(self.bg_label)
        bg_layout.addWidget(self.bg_btn)
        layout.addRow("WALLPAPER:", bg_layout)
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(["High Tech", "Retro", "Silent"])
        self.sound_combo.setCurrentText(current_sound)
        layout.addRow("AUDIO_FX:", self.sound_combo)
        btn_box = QHBoxLayout()
        apply_btn = GlowingButton("APPLY", NEON_GREEN)
        apply_btn.clicked.connect(self.apply)
        cancel_btn = GlowingButton("CANCEL", "#ff3333")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(apply_btn)
        btn_box.addWidget(cancel_btn)
        layout.addRow(btn_box)

    def choose_text_color(self):
        color = QColorDialog.getColor(QColor(self.selected_color), self, "Pick Text Color")
        if color.isValid():
            self.selected_color = color.name()
            self.color_btn.setText(self.selected_color)
            self.color_btn.update_color(self.selected_color)

    def choose_border_color(self):
        color = QColorDialog.getColor(QColor(self.selected_border), self, "Pick Border Color")
        if color.isValid():
            self.selected_border = color.name()
            self.border_btn.setText(self.selected_border)
            self.border_btn.update_color(self.selected_border)

    def choose_bg(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Wallpaper", "", "Images (*.png *.xpm *.jpg *.jpeg)")
        if fname:
            self.bg_path = fname
            self.bg_label.setText(os.path.basename(fname))

    def apply(self):
        self.settings_applied.emit(self.font_combo.currentFont(), self.selected_color, self.size_spin.value(), self.bg_path, self.sound_combo.currentText(), self.selected_border, self.model_combo.currentText())
        self.accept()

class TerminalOutput(QTextEdit):
    def __init__(self, font_family="Consolas", color=NEON_CYAN, size=13, border_color=NEON_PURPLE):
        super().__init__()
        self.setReadOnly(True)
        self.update_style(font_family, color, size, border_color)
    
    def update_style(self, font_family, color, size, border_color):
        self.setStyleSheet(f"QTextEdit {{ background-color: {TERM_BG_COLOR}; color: {color}; border: 1px solid {border_color}; border-radius: 5px; padding: 10px; font-family: '{font_family}'; font-size: {size}px; selection-background-color: {NEON_MAGENTA}; selection-color: black; }}")

class CyberpunkInput(QLineEdit):
    def __init__(self):
        super().__init__()
        self.update_style(NEON_MAGENTA, NEON_CYAN, 13, "Consolas")
        self.textEdited.connect(self.on_type)

    def update_style(self, text_color, border_color, size, font_family):
        self.setStyleSheet(f"QLineEdit {{ background-color: {INPUT_BG_COLOR}; color: {text_color}; border: 1px solid {border_color}; border-radius: 5px; padding: 8px; font-family: '{font_family}', monospace; font-size: {size}px; }} QLineEdit:focus {{ border: 1px solid #ffffff; background-color: rgba(30, 30, 40, 250); }}")

    def on_type(self, text):
        sound_manager.play_typing()
        
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key.Key_Delete:
             sound_manager.play_typing()

class GlowingButton(QPushButton):
    def __init__(self, text, color_hex, is_bold=True):
        super().__init__(text)
        self.is_bold = is_bold
        self.update_color(color_hex)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: sound_manager.play_typing())

    def update_color(self, color_hex):
        self.color_hex = color_hex
        weight = "bold" if self.is_bold else "normal"
        self.setStyleSheet(f"QPushButton {{ background-color: rgba(0, 0, 0, 150); color: {color_hex}; border: 1px solid {color_hex}; border-radius: 4px; padding: 6px 15px; font-family: 'Segoe UI', sans-serif; font-weight: {weight}; font-size: 11px; text-transform: uppercase; }} QPushButton:hover {{ background-color: {color_hex}; color: black; border: 1px solid #ffffff; }} QPushButton:pressed {{ background-color: white; color: black; }}")

class GeminiWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, prompt, model_name):
        super().__init__()
        self.prompt = prompt
        self.model_name = model_name

    def run(self):
        try:
            # Header-based Authentication (cURL style)
            headers = {
                'Content-Type': 'application/json',
                'X-goog-api-key': GEMINI_API_KEY
            }
            data = {
                "contents": [{
                    "parts": [{"text": self.prompt}]
                }]
            }
            
            # Dynamic Model URL
            clean_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            
            req = urllib.request.Request(
                clean_url, 
                data=json.dumps(data).encode('utf-8'), 
                headers=headers, 
                method='POST'
            )
            
            # Set timeout to prevents hangs
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                try:
                    text = result['candidates'][0]['content']['parts'][0]['text']
                    self.finished.emit(text)
                except (KeyError, IndexError, TypeError):
                    self.finished.emit("Error: Unexpected response format from AI.")
                    
        except urllib.error.HTTPError as e:
            try:
                # Try to parse the error body for a better message
                err_body = e.read().decode()
                err_json = json.loads(err_body)
                err_msg = err_json.get('error', {}).get('message', e.reason)
                
                if e.code == 429:
                    self.finished.emit(f"Rate Limited: {err_msg}. Please wait a moment.")
                elif e.code == 409:
                    self.finished.emit(f"Server Conflict (409): Please wait and retry. {err_msg}")
                else:
                    self.finished.emit(f"API Error {e.code}: {err_msg}")
            except:
                self.finished.emit(f"API Error: {e.code} {e.reason}")
                
        except urllib.error.URLError as e:
            self.finished.emit(f"Network Error: {e.reason}")
        except Exception as e:
            self.finished.emit(f"System Error: {str(e)}")

class AIChatWidget(QWidget):
    def __init__(self, parent=None, current_model="gemini-2.5-flash-lite"):
        super().__init__(parent)
        self.current_model = current_model
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 0, 0)
        self.layout.setSpacing(10)
        
        # Header
        self.header = QLabel(f">> AI ASSISTANT // ONLINE ({self.current_model})")
        self.header.setStyleSheet(f"color: {NEON_MAGENTA}; font-family: monospace; font-weight: bold; padding-bottom: 5px; border-bottom: 1px solid {NEON_PURPLE};")
        self.layout.addWidget(self.header)
        
        # Chat History
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        # ... (Styling remains same) ...
        self.chat_history.setStyleSheet(f"""
            QTextEdit {{ 
                background-color: {TERM_BG_COLOR}; 
                color: {NEON_CYAN}; 
                border: 1px solid {NEON_PURPLE}; 
                border-radius: 5px; 
                padding: 10px; 
                font-family: 'Consolas'; 
                font-size: 13px;
                selection-background-color: {NEON_MAGENTA};
                selection-color: black;
            }}
        """)
        self.layout.addWidget(self.chat_history)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(f"Ask {self.current_model}...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{ 
                background-color: {INPUT_BG_COLOR}; 
                color: white; 
                border: 1px solid {NEON_PURPLE}; 
                border-radius: 5px; 
                padding: 8px; 
                font-family: 'Consolas'; 
            }} 
            QLineEdit:focus {{ 
                border: 1px solid #ffffff; 
                background-color: rgba(30, 30, 40, 250); 
            }}
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        
        self.send_btn = GlowingButton("SEND", NEON_GREEN)
        self.send_btn.setFixedWidth(60)
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        
        self.layout.addLayout(input_layout)
        
        # Initial Message
        self.append_message("SYSTEM", f"Connected to {self.current_model}. Ready.", NEON_GREEN)

    def update_model(self, model_name):
        self.current_model = model_name
        self.header.setText(f">> AI ASSISTANT // ONLINE ({self.current_model})")
        self.input_field.setPlaceholderText(f"Ask {self.current_model}...")
        self.append_message("SYSTEM", f"Switched model into: {model_name}", NEON_MAGENTA)

    def send_message(self):
        msg = self.input_field.text().strip()
        if not msg: return
        
        self.append_message("YOU", msg, "white")
        self.input_field.clear()
        self.input_field.setDisabled(True) # Disable input while processing
        self.send_btn.setDisabled(True)
        self.header.setText(f">> AI ASSISTANT // THINKING...")
        
        # Start Worker Thread
        self.worker = GeminiWorker(msg, self.current_model)
        self.worker.finished.connect(self.handle_response)
        self.worker.start()
        
    def handle_response(self, response_text):
        self.append_message("GEMINI", response_text, NEON_CYAN)
        self.input_field.setDisabled(False)
        self.send_btn.setDisabled(False)
        self.input_field.setFocus()
        self.header.setText(f">> AI ASSISTANT // ONLINE ({self.current_model})")

    def append_message(self, sender, text, color):
        # Parse Markdown for AI responses
        formatted_text = text
        if sender not in ["YOU", "SYSTEM"]:
            try:
                formatted_text = markdown.markdown(text, extensions=['fenced_code', 'codehilite'])
            except Exception:
                pass # Fallback to plain text
        
        # Replace newlines with <br> for plain text if not HTML (basic check)
        if formatted_text == text:
             formatted_text = text.replace("\n", "<br>")
             
        # Format bold for sender
        html_msg = f"<span style='color: {color}; font-weight: bold;'>[{sender}]</span> <span style='color: #dddddd;'>{formatted_text}</span>"
        self.chat_history.append(html_msg)
        self.chat_history.append("") # Spacing
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)
        sound_manager.play_typing()

class CyberpunkShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CYBERPUNK SHELL GUI")
        self.resize(WINDOW_WIDTH + 250, WINDOW_HEIGHT) # Expand for AI sidebar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.old_pos = None
        self.current_font = QFont("Consolas")
        self.current_color = NEON_CYAN
        self.current_size = 13
        self.current_border = NEON_PURPLE
        self.current_model = "gemini-2.5-flash-lite" # Default Model
        self.last_error = None
        
        # Session Timer
        self.start_time = time.time()
        self.timer_timer = QTimer(self)
        self.timer_timer.timeout.connect(self.update_timer)
        self.timer_timer.start(1000)
        
        # ... (Timers remain same) ...
        # Resource Monitor Timer
        self.res_timer = QTimer(self)
        self.res_timer.timeout.connect(self.update_resources)
        self.res_timer.start(2000) # Update every 2s

        if os.path.exists(DEFAULT_BG_PATH): self.current_bg = os.path.abspath(DEFAULT_BG_PATH)
        else: self.current_bg = ""
        self.current_sound = "High Tech"
        self.init_ui()
        self.init_process()
        self.update_resources() # Initial call
        sound_manager.play_startup()
    
    # ... (Update methods remain same) ...
    def update_timer(self):
        elapsed = int(time.time() - self.start_time)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        self.timer_label.setText(f"UPTIME: {hrs:02}:{mins:02}:{secs:02}")
    
    def update_resources(self):
        # Default mock values
        cpu_usage = 12
        mem_usage_str = "64TB" 
        
        if HAS_PSUTIL:
             try:
                 cpu_usage = int(psutil.cpu_percent())
                 mem = psutil.virtual_memory()
                 # Convert to GB
                 total_gb = mem.total / (1024**3)
                 used_gb = mem.used / (1024**3)
                 mem_usage_str = f"{used_gb:.1f}/{total_gb:.0f}GB"
             except: pass
        else:
            # Fallback for Windows
            if platform.system() == "Windows":
                 import ctypes
                 class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                 try:
                     stat = MEMORYSTATUSEX()
                     stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                     ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                     total_gb = stat.ullTotalPhys / (1024**3)
                     avail_gb = stat.ullAvailPhys / (1024**3)
                     used_gb = total_gb - avail_gb
                     mem_usage_str = f"{used_gb:.1f}/{total_gb:.0f}GB"
                 except: pass # Keep mock default
                 
        self.mem_label.setText(f"MEM: {mem_usage_str} // CPU: {cpu_usage}% // NET: SECURE")

    def init_ui(self):
        # ... (Basic UI init remains same) ...
        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, WINDOW_WIDTH + 300, WINDOW_HEIGHT)
        self.bg_label.setScaledContents(True)
        self.update_background()
        self.main_frame = QFrame(self)
        self.setCentralWidget(self.main_frame)
        self.update_main_frame_style()
        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35) # Force reduced height
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(10, 2, 10, 2) # Reduced margins
        self.title_bar_layout.setSpacing(10)
        self.update_title_bar_style()
        title_label = QLabel(">> ADV_SHELL.EXE // v3.0 // AI ENABLED")
        title_label.setStyleSheet(f"color: {self.current_color}; font-family: monospace; font-weight: bold; border: none;")
        self.title_bar_layout.addWidget(title_label)
        self.title_bar_layout.addStretch()
        
        # Timer Label in Title Bar
        self.timer_label = QLabel("UPTIME: 00:00:00")
        self.timer_label.setStyleSheet(f"color: {self.current_color}; font-family: monospace; padding-right: 15px;")
        self.title_bar_layout.addWidget(self.timer_label)
        
        btn_settings = GlowingButton("CFG", "#ffffff", False)
        btn_settings.setFixedSize(30, 20)
        btn_settings.clicked.connect(self.open_settings)
        btn_min = GlowingButton("_", self.current_color, False)
        btn_min.setFixedSize(25, 20)
        btn_min.clicked.connect(self.showMinimized)
        btn_close = GlowingButton("X", "#ff3333", False)
        btn_close.setFixedSize(25, 20)
        btn_close.clicked.connect(self.close)
        self.title_bar_layout.addWidget(btn_settings)
        self.title_bar_layout.addSpacing(5)
        self.title_bar_layout.addWidget(btn_min)
        self.title_bar_layout.addSpacing(5)
        self.title_bar_layout.addWidget(btn_close)
        layout.addWidget(self.title_bar)
        
        # --- SPLIT SCREEN LAYOUT ---
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 0, 10, 10) # Reduced top margin
        content_layout.setSpacing(10)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {self.current_border}; }}")
        
        # Left Side: Shell
        self.shell_widget = QWidget()
        shell_layout = QVBoxLayout(self.shell_widget)
        shell_layout.setContentsMargins(0, 0, 10, 0)
        shell_layout.setSpacing(10)
        
        self.terminal = TerminalOutput(self.current_font.family(), self.current_color, self.current_size, self.current_border)
        shell_layout.addWidget(self.terminal)
        
        # Status Line
        status_layout = QHBoxLayout()
        self.mem_label = QLabel("MEM: INIT... // CPU: 0% // NET: SECURE")
        self.mem_label.setStyleSheet(f"color: {NEON_GREEN}; font-size: 10px; font-family: monospace;")
        status_layout.addWidget(self.mem_label)
        status_layout.addStretch()
        shell_layout.addLayout(status_layout)
        
        input_container = QHBoxLayout()
        input_container.setAlignment(Qt.AlignmentFlag.AlignVCenter) # Strict vertical centering
        label_prompt = QLabel("$>")
        label_prompt.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label_prompt.setStyleSheet(f"color: {NEON_MAGENTA}; font-size: 16px; font-weight: bold; font-family: monospace; border: none; padding-bottom: 2px;")
        input_container.addWidget(label_prompt)
        self.input_field = CyberpunkInput()
        self.input_field.update_style(self.current_color, self.current_border, self.current_size, self.current_font.family())
        self.input_field.returnPressed.connect(self.send_command)
        input_container.addWidget(self.input_field)
        self.btn_run = GlowingButton("EXECUTE", self.current_color)
        self.btn_run.clicked.connect(self.send_command)
        self.btn_clear = GlowingButton("PURGE", "#ffff00")
        self.btn_clear.clicked.connect(self.terminal.clear)
        self.btn_kill = GlowingButton("KILL", "#ff3333")
        self.btn_kill.clicked.connect(self.kill_process)
        input_container.addWidget(self.btn_run)
        input_container.addWidget(self.btn_clear)
        input_container.addWidget(self.btn_kill)
        shell_layout.addLayout(input_container)
        
        # Right Side: AI
        self.ai_widget = AIChatWidget(current_model=self.current_model)
        
        # Add to Splitter
        self.splitter.addWidget(self.shell_widget)
        self.splitter.addWidget(self.ai_widget)
        self.splitter.setSizes([int(WINDOW_WIDTH * 0.7), int(WINDOW_WIDTH * 0.3)])
        
        content_layout.addWidget(self.splitter)
        layout.addWidget(content_widget)

        # Size Grip (Bottom Right)
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background-color: transparent;") 
        grip_layout.addWidget(self.size_grip)
        layout.addLayout(grip_layout)


    def update_main_frame_style(self):
        self.main_frame.setStyleSheet(f"QFrame {{ background-color: rgba(0, 0, 0, 40); border: 1px solid {self.current_border}; border-radius: 10px; }}")

    def update_title_bar_style(self):
         self.title_bar.setStyleSheet(f"background-color: rgba(0, 0, 0, 80); border: none; border-bottom: 1px solid {self.current_border};")

    def open_settings(self):
        dialog = SettingsDialog(self.current_font, self.current_color, self.current_size, self.current_bg, self.current_sound, self.current_border, self.current_model, self)
        dialog.settings_applied.connect(self.apply_new_settings)
        dialog.exec()

    def apply_new_settings(self, font, color, size, bg_path, sound_theme, border_color, model_name):
        self.current_font = font
        self.current_color = color
        self.current_size = size
        self.current_border = border_color
        self.current_model = model_name
        self.terminal.update_style(font.family(), color, size, border_color)
        self.input_field.update_style(color, border_color, size, font.family())
        self.update_main_frame_style()
        self.update_title_bar_style()
        self.btn_run.update_color(color)
        if bg_path != self.current_bg:
            self.current_bg = bg_path
            self.update_background()
        if sound_theme != self.current_sound:
            self.current_sound = sound_theme
            sound_manager.set_theme(sound_theme)
        
        # Update AI Model
        self.ai_widget.update_model(model_name)

    def update_background(self):
        if self.current_bg and os.path.exists(self.current_bg):
             self.bg_label.setPixmap(QPixmap(self.current_bg))
        else:
             self.bg_label.setStyleSheet("background-color: #050011;")

    def resizeEvent(self, event):
        if hasattr(self, 'bg_label'):
             self.bg_label.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def init_process(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)
        
        cmd_to_run = SHELL_CMD_MOCK if platform.system() == "Windows" else SHELL_CMD_LINUX
        if platform.system() != "Windows":
             if not os.path.exists("./advsh"):
                 if os.path.exists("shell.c"):
                     self.terminal.append("<span style='color: orange;'>[SYSTEM] 'advsh' not found. Compiling shell.c...</span>")
                     compile_result = os.system("gcc shell.c -o advsh")
                     if compile_result == 0:
                          self.terminal.append("<span style='color: #39ff14;'>[SYSTEM] Compilation successful.</span>")
                          os.system("chmod +x advsh")
                          cmd_to_run = "./advsh"
                     else:
                          msg = "[ERROR] Compilation failed! Ensure gcc is installed."
                          self.terminal.append(f"<span style='color: red;'>{msg}</span>")
                          self.last_error = msg
                          return
                 else:
                     msg = "[ERROR] 'advsh' binary AND 'shell.c' missing! Cannot start shell."
                     self.terminal.append(f"<span style='color: red;'>{msg}</span>")
                     self.last_error = msg
                     return
             else:
                 cmd_to_run = "./advsh"
        
        program = ""
        args = []
        if "python" in cmd_to_run:
            program = sys.executable 
            script_path = cmd_to_run.split(" ")[1]
            if not os.path.exists(script_path):
                 msg = f"ERROR: {script_path} not found!"
                 self.terminal.append(f"<span style='color: red;'>{msg}</span>")
                 self.last_error = msg
                 return
            args = [script_path]
        else:
            program = cmd_to_run
            args = []
        self.terminal.append(f"<span style='color: white;'>Launching: {program} {args}</span>")
        self.process.start(program, args)
        if not self.process.waitForStarted(1000): pass

    def handle_process_error(self, error):
        err_msg = "Unknown Error"
        if error == QProcess.ProcessError.FailedToStart: err_msg = "Failed To Start (Check permissions/path)"
        elif error == QProcess.ProcessError.Crashed: err_msg = "Process Crashed"
        elif error == QProcess.ProcessError.Timedout: err_msg = "Timed Out"
        elif error == QProcess.ProcessError.WriteError: err_msg = "Write Error"
        elif error == QProcess.ProcessError.ReadError: err_msg = "Read Error"
        
        msg = f"[SYSTEM ERROR] {err_msg}"
        self.terminal.append(f"<span style='color: red;'>{msg}</span>")
        self.last_error = msg

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        text = data.data().decode('utf-8', errors='replace').strip()
        if text:
            text_lower = text.lower()
            error_keywords = ["not found", "error", "failed", "denied", "usage:", "invalid"]
            if any(k in text_lower for k in error_keywords):
                self.last_error = text
            self.terminal.append(text)
            cursor = self.terminal.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.terminal.setTextCursor(cursor)

    def send_command(self):
        cmd = self.input_field.text().strip()
        if not cmd: return
        sound_manager.play_enter()
        self.terminal.append(f"<span style='color: {NEON_MAGENTA};'>$ {cmd}</span>")
        if cmd_manager.handle_command(cmd, self):
            self.input_field.clear()
            return
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.write((cmd + "\n").encode('utf-8'))
        else:
            msg = "[ERROR] SHELL HALTED. RESTART APP."
            self.terminal.append(f"<span style='color: red;'>{msg}</span>")
            self.last_error = msg
        self.input_field.clear()

    def kill_process(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
        self.terminal.append("<span style='color: red;'>[SYSTEM] TERMINATED. CLOSING...</span>")
        # Close the app after a tiny delay to show the message
        QTimer.singleShot(500, self.close)
    
    def force_kill_if_running(self):
        # Deprecated logic, simplified above
        pass

    def process_finished(self, exit_code, exit_status):
        status_str = "Normal Exit" if exit_status == 0 else "Crash/Kill"
        self.terminal.append(f"<span style='color: gray;'>[SYSTEM] PROCESS ENDED. Code: {exit_code} ({status_str})</span>")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Consolas", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(font)
    window = CyberpunkShell()
    window.show()
    sys.exit(app.exec())
