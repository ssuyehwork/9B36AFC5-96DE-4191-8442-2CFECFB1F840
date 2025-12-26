# -*- coding: utf-8 -*-
import sys
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# === 配置日志 ===
# 创建日志格式
log_format = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)

# 文件输出
file_handler = logging.FileHandler('debug_main.log', encoding='utf-8', mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_format)

# 配置根日志
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

log = logging.getLogger("MainEntry")

def exception_hook(exctype, value, tb):
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    log.critical(f"🔥 崩溃信息:\n{error_msg}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

def main():
    log.info("🚀 启动印象记忆_Pro (主界面版)...")
    
    # 高 DPI 适配
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("ClipboardManagerPro_Main")
    
    # 单实例检测 (使用不同的锁名称，允许 QuickPanel 和 Main 同时运行)
    from PyQt5.QtCore import QSharedMemory
    shared_mem = QSharedMemory("ClipboardPro_Main_Instance")
    
    if shared_mem.attach():
        # 如果主界面已经在运行，则退出
        log.info("⚠️ 主界面已在运行中。")
        return
    else:
        # 创建锁
        if not shared_mem.create(1):
            log.error("❌ 无法创建单实例锁")
            return

    try:
        # === 核心修改：从 ui 包导入 main_window ===
        # 因为文件结构是:
        # root/ClipboardPro_2.py
        # root/ui/main_window.py
        from ui.main_window import MainWindow
        
        # 创建主窗口实例
        window = MainWindow()
        
        window.show()
        
        # 窗口居中逻辑
        screen_geo = app.desktop().screenGeometry()
        window_geo = window.geometry()
        window.move(
            (screen_geo.width() - window_geo.width()) // 2,
            (screen_geo.height() - window_geo.height()) // 2
        )
        
        sys.exit(app.exec_())
        
    except Exception as e:
        log.critical(f"❌ 启动失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()