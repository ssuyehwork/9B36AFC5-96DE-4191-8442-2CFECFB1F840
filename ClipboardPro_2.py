# -*- coding: utf-8 -*-
import sys
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject

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

        # 根据您的要求，同时显示悬浮球和快速面板
        self.ball.show()
        self.quick_panel.show()
        self.tray.show()

    def _connect_signals(self):
        # 悬浮球信号
        self.ball.request_show_quick_window.connect(self.toggle_quick_panel)
        self.ball.double_clicked.connect(self.toggle_quick_panel)
        self.ball.request_show_main_window.connect(self.quick_panel._launch_main_app)
        self.ball.request_quit_app.connect(self.app.quit)

        # 托盘图标信号
        self.tray.request_show_quick_panel.connect(self.toggle_quick_panel)
        self.tray.request_quit.connect(self.app.quit)

    def toggle_quick_panel(self):
        if self.quick_panel.isVisible():
            self.quick_panel.hide()
        else:
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
    # 关键：防止在最后一个窗口关闭时退出程序，除非显式调用 quit()
    app.setQuitOnLastWindowClosed(False)
    
    from PyQt5.QtCore import QSharedMemory
    shared_mem = QSharedMemory("ClipboardPro_Main_Instance_Lock_v2")
    
    if shared_mem.attach():
        log.info("⚠️ 应用已在运行中.")
        return
    else:
        if not shared_mem.create(1):
            log.error("❌ 无法创建单实例锁")
            return

    try:
        controller = AppController(app)
        sys.exit(app.exec_())
    except Exception as e:
        log.critical(f"❌ 启动失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()
