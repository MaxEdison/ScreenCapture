

# Screen Capture 🖥️ 📸

ScreenCapture is a simple Python application that allows you to share your screen in local network over HTTP. It provides a convenient way to share your screen in real-time.

## Features ✨

-   **Live Screen Streaming:** Capture screenshots continuously and stream them to a web page in real-time.
-   **Multi-threaded:** Utilizes multi-threading to handle multiple client connections simultaneously.
-   **JPEG Format:** Screenshots are encoded in JPEG format for efficient transmission over the network.
-   **Customizable:** Easily customize the server settings such as host, port, and streaming intervals according to your requirements.

## Usage 🚀

**Windows:**
1. Install **Python 3**:
Download and Install Python 3 From [www.python.org](https://www.python.org/downloads/)<br >

2. Clone the repository:

```bash
git clone https://github.com/MaxEdison/ScreenCapture
```

3. Install the required dependencies:
Simply Run "**windows-install.bat**" to install all dependencies OR use this command:
```bash
pip install -r requirements.txt
```

4. Run the server:
Simply Run "**windows-run.bat**" OR use this command:

```bash
python main.py
```

Now clients can stream your screen by entering your machine IP address on **port 8000** (default port)

You can find your IP address in local network by this command:

```bash
ipconfig
```

**Linux/MacOS:**

1. Clone the repository:

```bash
git clone https://github.com/MaxEdison/ScreenCapture
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Run the server:

```bash
python main.py
```

Now clients can stream your screen by entering your machine IP address on **port 8000** (default port)

You can find your IP address in local network by this command:

```bash
ifconfig
```

## Dependency 📦

[PyAutoGUI](https://pyautogui.readthedocs.io/): Python library for automating keyboard and mouse actions. <br />[TKinter](https://docs.python.org/3/library/tk.html): The tkinter package (“Tk interface”) is the standard Python interface to the Tcl/Tk GUI toolkit. 

## Contributing 🤝

Contributions are always welcome!

If you find any issues or have suggestions for improvements, feel free to open an issue or submit a pull request.

## License 📄

[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)

## Acknowledgement 🙏

This project was inspired by [ScreenTask](https://github.com/EslaMx7/ScreenTask).

(ScreenTask is only available on Windows).

-   [ScreenTask Website](https://screentask.me/)
