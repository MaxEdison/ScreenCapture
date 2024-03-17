###################################################
#     https://github.com/MaxEdison/ScreenCapture  #
#                                                 #
#      Max Edison - AmirHossein Heidari           #
#                                                 #
#                Screen Capture                   # 
###################################################


import socketserver

class ScreenCapture(socketserver.BaseRequestHandler):
    def handle():
        pass

HOST = "0.0.0.0"
PORT = 8000

with socketserver.ThreadingTCPServer((HOST, PORT), ScreenCapture) as httpServer:
    print(f"Start HTTP server on {HOST}:{PORT}")
    httpServer.serve_forever()
