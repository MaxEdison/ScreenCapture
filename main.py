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

class ScreenCapture(socketserver.BaseRequestHandler):
    def handle():

        self.request.sendall(b"HTTP/1.1 200 OK\r\n")
        self.request.sendall(b"Content-type: multipart/x-mixed-replace; boundary=frame\r\n")
        self.request.sendall(b"\r\n")

        while True:
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

HOST = "0.0.0.0"
PORT = 8000

with socketserver.ThreadingTCPServer((HOST, PORT), ScreenCapture) as httpServer:
    print(f"Start HTTP server on {HOST}:{PORT}")
    httpServer.serve_forever()
