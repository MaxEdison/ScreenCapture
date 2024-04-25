###################################################
#     https://github.com/MaxEdison/ScreenCapture  #
#                                                 #
#      Max Edison - AmirHossein Heidari           #
#                                                 #
#                Screen Capture                   # 
###################################################


import socketserver
import threading
import pyautogui
import io
import socket
import tkinter as tk
from tkinter import font
import os

class ScreenCapture(socketserver.BaseRequestHandler):
    is_running = True

    def handle(self):
        self.request.sendall(b"HTTP/1.1 200 OK\r\n")
        self.request.sendall(b"Content-type: multipart/x-mixed-replace; boundary=frame\r\n")
        self.request.sendall(b"\r\n")

        while self.is_running:
            scrnsht = pyautogui.screenshot()
            BinImg = io.BytesIO()
            scrnsht.save(BinImg, format='JPEG')
            BinImg.seek(0)

            self.request.sendall(b"--frame\r\n")
            self.request.sendall(b"Content-type: image/jpeg\r\n")
            self.request.sendall(f"Content-length: {len(BinImg.getvalue())}\r\n".encode())
            self.request.sendall(b"\r\n")
            self.request.sendall(BinImg.getvalue())
            self.request.sendall(b"\r\n")

def get_private_ip():
    private_ip = None

    try:
        if os.name == "nt":
            ip = os.popen("ipconfig").read()
            for line in ip.split('\n'):
                if 'IPv4' in line:
                    line = line.split()
                    idx = line.index(':')
                    return line[idx+1]
        
        else:
            ip = os.popen("ip -o addr show | grep lan | awk '{print $2 , $4}'").read()

            for line in ip.split('\n'):
                line = line.split()
                return line[1]
                    
    except:
        private_ip = 'Unable to get private IP address'

    return private_ip

HOST = "0.0.0.0"
PORT = 8000
httpServer = None

def start_server():
    global httpServer
    httpServer = socketserver.ThreadingTCPServer((HOST, PORT), ScreenCapture)
    label.config(text=
f"""
Status: HTTP server ON

Users can connect through the following IP: {get_private_ip()}:{8000}

Please do not close the window!
""")
    httpServer.serve_forever()

def start_function():
    global httpServer
    if not httpServer:
        ScreenCapture.is_running = True
        thread = threading.Thread(target=start_server)
        thread.daemon = True
        thread.start()
        httpServer = True
        

def stop_function():
    global httpServer
    ScreenCapture.is_running = False
    label.config(text=f"Status: HTTP server OFF")
    if httpServer:
        httpServer.shutdown()
        httpServer.server_close()
        httpServer = False

root = tk.Tk()
root.configure()
root['pady'] = 100
root.title("SCREEN CAPTURE")
root.geometry("400x500")
root.resizable(False, False)
label_font = font.Font(weight="bold")


start_button = tk.Button(root, text="Start", command=start_function, width=15,bg='#10AC84',fg='white', height=5, font=label_font)
start_button.pack()


stop_button = tk.Button(root, text="Stop", command=stop_function, width=15,bg='#EE5253',fg='white', height=5, font=label_font)
stop_button.pack()


label = tk.Label(root)
label.pack()

root.mainloop()
