# -*- coding: utf-8 -*-
import sys
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

# === 配置日志 ===
log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
log = logging.getLogger("MainEntry")

def exception_hook(exctype, value, tb):
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    log.critical(f"🔥 崩溃信息:\n{error_msg}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

# --- App Controller ---
class AppController(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        
        from data.database import DBManager
        from quick import MainWindow as QuickPanelWindow
        from ui.ball import FloatingBall
        from ui.tray_manager import TrayManager
        
        self.db_manager = DBManager()
        self.quick_panel = QuickPanelWindow(db_manager=self.db_manager)
        self.ball = FloatingBall(main_window=self.quick_panel)
        self.tray = TrayManager()
        
        self._connect_signals()
        
        self.ball.show()
        self.quick_panel.show()
        self.tray.show()

    def _connect_signals(self):
        self.ball.request_show_quick_window.connect(self.toggle_quick_panel)
        self.ball.double_clicked.connect(self.toggle_quick_panel)
        self.ball.request_show_main_window.connect(self.quick_panel._launch_main_app)
        self.ball.request_quit_app.connect(self.app.quit)
        
        self.tray.request_show_quick_panel.connect(self.toggle_quick_panel)
        self.tray.request_quit.connect(self.app.quit)
        
    def toggle_quick_panel(self):
        if self.quick_panel.isVisible():
            self.quick_panel.hide()
        else:
            self.quick_panel.show()
            self.quick_panel.activateWindow()
            self.quick_panel.raise_()
            
    def activate_window(self):
        """激活并显示快速面板"""
        self.quick_panel.show()
        self.quick_panel.activateWindow()
        self.quick_panel.raise_()

def main():
    log.info("🚀 启动印象记忆_Pro...")
    
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("ClipboardManagerPro")
    app.setQuitOnLastWindowClosed(False)
    
    # --- 单例逻辑 ---
    server_name = "ClipboardPro_Instance_Server"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    
    if socket.waitForConnected(500):
        log.info("⚠️ 应用已在运行中, 激活现有窗口.")
        socket.write(b'RAISE')
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return # 新实例退出
        
    # 没有现有实例，创建服务器
    server = QLocalServer()
    server.listen(server_name)

    try:
        controller = AppController(app)
        
        # 连接服务器的新连接信号
        def handle_new_connection():
            new_socket = server.nextPendingConnection()
            if new_socket:
                new_socket.waitForReadyRead(1000)
                command = new_socket.readAll().data().decode()
                if command == 'RAISE':
                    log.info("收到激活请求, 正在显示窗口...")
                    controller.activate_window()
                new_socket.disconnectFromServer()

        server.newConnection.connect(handle_new_connection)
        
        sys.exit(app.exec_())
    except Exception as e:
        log.critical(f"❌ 启动失败: {e}", exc_info=True)
    finally:
        # 清理服务器
        server.close()
        server.removeServer(server_name)

if __name__ == "__main__":
    main()
