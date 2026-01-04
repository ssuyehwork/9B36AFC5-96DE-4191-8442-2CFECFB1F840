# -*- coding: utf-8 -*-
import sys
import logging
import traceback
import sys
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

# 组件导入
from data.database import DBManager
from quick import MainWindow as QuickPanelWindow
from ui.ball import FloatingBall
from ui.tray_manager import TrayManager
from ui.action_popup import ActionPopup
from ui.common_tags_manager import CommonTagsManager

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
        
        self.db_manager = DBManager()
        self.quick_panel = QuickPanelWindow(db_manager=self.db_manager)
        self.ball = FloatingBall(main_window=self.quick_panel)
        self.tray = TrayManager()
        self.action_popup = ActionPopup()
        self.main_window_instance = None # 持有主窗口实例
        
        self._connect_signals()
        
        self.ball.show()
        self.quick_panel.show()
        self.tray.show()

    def _connect_signals(self):
        # Connect clipboard capture signal to ball's feedback animation
        self.quick_panel.cm.data_captured.connect(self.ball.trigger_clipboard_feedback)
        self.quick_panel.cm.data_captured.connect(self.on_data_captured)

        # Connect ActionPopup signals
        self.action_popup.request_favorite.connect(lambda item_id: self.db_manager.update_item(item_id, is_favorite=True))
        self.action_popup.request_tag_add.connect(self.db_manager.add_tags_to_items)
        self.action_popup.request_manager.connect(self._show_common_tags_manager)

        self.ball.request_show_quick_window.connect(self.toggle_quick_panel)
        self.ball.double_clicked.connect(self.toggle_quick_panel)
        self.ball.request_show_main_window.connect(self._show_main_window)
        self.ball.request_show_tag_manager.connect(self._show_common_tags_manager)
        self.ball.request_quit_app.connect(self.app.quit)
        
        # 连接快速面板的信号
        self.quick_panel.request_show_main_window.connect(self._show_main_window)

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

    def _show_common_tags_manager(self):
        """显示常用标签管理对话框"""
        # Prevent creating multiple instances
        if not hasattr(self, 'common_tags_manager_dialog') or not self.common_tags_manager_dialog.isVisible():
            self.common_tags_manager_dialog = CommonTagsManager(self.quick_panel)
            self.common_tags_manager_dialog.show()

    def _show_main_window(self):
        """创建并显示主数据管理窗口"""
        try:
            if self.main_window_instance and self.main_window_instance.isVisible():
                self.main_window_instance.activateWindow()
                self.main_window_instance.raise_()
                log.info("主窗口已存在，激活并置顶。")
            else:
                log.info("主窗口不存在或已关闭，正在创建新实例...")
                from ui.main_window import MainWindow

                self.main_window_instance = MainWindow()
                self.main_window_instance.show()

                # 居中显示
                screen_geo = QApplication.desktop().screenGeometry()
                window_geo = self.main_window_instance.geometry()
                self.main_window_instance.move(
                    (screen_geo.width() - window_geo.width()) // 2,
                    (screen_geo.height() - window_geo.height()) // 2
                )
                log.info("✅ 主窗口创建并显示成功。")

        except Exception as e:
            log.error(f"❌ 启动主窗口失败: {e}", exc_info=True)

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
