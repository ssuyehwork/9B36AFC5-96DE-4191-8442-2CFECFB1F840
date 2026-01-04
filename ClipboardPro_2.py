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
        
        from data.database import DatabaseManager as DBManager
        from quick import QuickWindow as QuickPanelWindow
        from ui.ball import FloatingBall
        from ui.tray_manager import TrayManager
        from ui.action_popup import ActionPopup
        
        self.db_manager = DBManager()
        self.quick_panel = QuickPanelWindow(db_manager=self.db_manager)
        self.ball = FloatingBall(main_window=self.quick_panel)
        self.tray = TrayManager()
        self.action_popup = ActionPopup()
        
        self._connect_signals()
        
        self.ball.show()
        self.quick_panel.show()
        self.tray.show()

    def _connect_signals(self):
        # Connect clipboard capture signal to ball's feedback animation
        self.quick_panel.cm.data_captured.connect(self.ball.trigger_clipboard_feedback)
        self.quick_panel.cm.data_captured.connect(self.on_data_captured)

        # Connect ActionPopup signals
        self.action_popup.request_favorite.connect(lambda item_id: self.db_manager.set_favorite(item_id, True))
        self.action_popup.request_tag_add.connect(lambda item_id, tag_names: self.db_manager.add_tags_to_multiple_ideas([item_id], tag_names))
        self.action_popup.request_manager.connect(self._launch_main_app)

        self.ball.request_show_quick_window.connect(self.toggle_quick_panel)
        self.ball.double_clicked.connect(self.toggle_quick_panel)
        self.ball.request_show_main_window.connect(self._launch_main_app)
        self.ball.request_quit_app.connect(self.app.quit)
        
        # Connect quick panel's request to launch main window
        self.quick_panel.toggle_main_window_requested.connect(self._launch_main_app)

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

    def on_data_captured(self, item, is_new):
        """当剪贴板捕获到新数据时，显示快捷操作条"""
        if is_new and item:
            self.action_popup.show_at_mouse(item.id)

    def _launch_main_app(self):
        """启动主程序窗口（占位）"""
        log.info("🚀 请求启动主程序窗口...")
        # 在这里添加启动主窗口的逻辑
        # from ui.main_window import MainWindow
        # if not hasattr(self, 'main_window') or not self.main_window.isVisible():
        #     self.main_window = MainWindow(self.db_manager)
        #     self.main_window.show()
        # else:
        #     self.main_window.activateWindow()

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
