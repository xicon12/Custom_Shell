# CyberShell Hybrid 🚀

A high-performance, Linux-based C shell engine wrapped in a stunning Cyberpunk-themed Python GUI. CyberShell bridges the gap between low-level system operations and modern AI-enhanced user experience.

![CyberShell Screenshot](screenshot_2698.png)

## ✨ Features

### 🛠️ Core Shell Engine (Backend in C)
- **Command Execution:** Run standard system commands with full argument support.
- **Pipeline Support (`|`):** Chain multiple commands together seamlessly.
- **I/O Redirection:** Direct input/output using `<`, `>`, and `>>`.
- **Job Control:** Manage background processes with `jobs`, `fg`, and `bg`.
- **Signal Handling:** Robust handling of `Ctrl+C`, `Ctrl+Z`, and process reaping.
- **Persistent History:** Automatically saves and reloads command history across sessions.

### 🎨 Cyberpunk GUI (Frontend in PyQt6)
- **Immersive Aesthetic:** Translucent, frameless window with neon glow effects and custom wallpapers.
- **Integrated AI Assistant:** Real-time side-panel chat powered by **Google Gemini**.
- **System Monitoring:** Live dashboard for CPU, RAM, and Uptime.
- **Audio Feedback:** Themeable sound effects for typing and system events.
- **Split-Screen Design:** Resizable terminal and AI interfaces.
- **Customizable:** Change fonts, colors, and backgrounds on the fly.

### 🪄 Magic Commands
Special commands handled directly by the GUI:
- `game`: Launch the built-in **Snake Protocol** game.
- `screenshot`: Instantly capture your terminal screen.
- `weather`: Quick browser-based weather updates.
- `joke` / `fact` / `motivation`: Built-in tokens of entertainment.
- `website <url>`: Fast-launch any URL.

## 🚀 Getting Started

### Prerequisites
- **Linux** (Core shell uses Linux system calls) or **WSL** on Windows.
- **Python 3.8+**
- **GCC Compiler** (for the C backend)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/xicon12/Custom_Shell.git
   cd Custom_Shell
   ```

2. **Build the C Shell:**
   ```bash
   make
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Gemini AI (Optional):**
   - Copy `.env.example` to `.env`.
   - Add your [Gemini API Key](https://aistudio.google.com/app/apikey).
   ```bash
   cp .env.example .env
   # Edit .env and add your key
   ```

### Running the App
```bash
python cyberpunk_shell_gui.py
```

## 🏗️ Architecture
CyberShell follows a **Two-Tier Architecture**:
1. **Low-Level Logic (C):** Manages process forking, memory, pipes, and OS kernel interaction.
2. **Presentation Layer (Python):** A PyQt6 wrapper that communicates with the C backend via standard streams (stdin/stdout/stderr), providing AI integration and rich visuals.

## 📄 License
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---
*Built with ⚡ by Shahe*
