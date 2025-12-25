# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QPoint, QTimer
from ui.popup_tag import TagPopup
from ui.widget_tag_input import TagInputWidget

class TagPanel(QWidget):
    """标签面板（集成输入组件和弹窗）"""
    # 信号定义
    tag_selected = pyqtSignal(str)
    tags_committed = pyqtSignal(list)    # 回车提交
    add_tag_requested = pyqtSignal(str)  # 兼容旧代码
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("TagPanel")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 22, 10, 12) # 左右边距设为 10，保持与左侧面板一致
        self.layout.setSpacing(10)
        
        # 1. 输入组件（上下结构）
        self.input_widget = TagInputWidget()
        self.input_widget.line_edit.installEventFilter(self)  # 监听底层输入框
        
        # 连接信号
        self.input_widget.text_changed.connect(self._on_text_changed)
        self.input_widget.tags_committed.connect(self._on_tags_committed)
        # 当暂存区变化时，同步更新弹窗的勾选状态
        self.input_widget.tags_changed.connect(self._on_chips_updated)
        
        self.layout.addWidget(self.input_widget)
        self.layout.addStretch()
        
        # 2. 悬浮弹窗
        self.popup = TagPopup(self)
        # 设为 Popup 模式：点击外部自动关闭
        self.popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.popup.setFocusPolicy(Qt.NoFocus)
        self.popup.hide()
        
        # 弹窗信号
        self.popup.tag_selected.connect(self._on_popup_tag_toggle)         # 历史标签勾选
        self.popup.create_tag_requested.connect(self._on_create_new_tag)   # 新词点击
        
        self.cached_tags = []

    def eventFilter(self, obj, event):
        """核心交互逻辑"""
        if obj == self.input_widget.line_edit:
            # === 严格执行双击逻辑 ===
            # 单击不再响应，只有双击才弹出历史
            if event.type() == QEvent.MouseButtonDblClick:
                if not self.popup.isVisible():
                    QTimer.singleShot(50, self._show_history_popup)
                    
        return super().eventFilter(obj, event)

    def _show_history_popup(self):
        """显示历史标签面板"""
        # 如果此时输入框有文字，显示过滤结果；没文字，显示纯历史
        current_text = self.input_widget.current_text().strip()
        self.popup.load_history(self.cached_tags, self.input_widget.get_tags())
        
        if current_text:
            self.popup.filter_ui(current_text)  # 有字显示筛选/新词
        else:
            self.popup.filter_ui("")  # 没字显示历史
            
        self._position_popup()
        self.popup.show()
        
        # 保持焦点在输入框
        self.input_widget.set_focus()

    def _on_text_changed(self, text):
        """输入文字变化 -> 决策弹出内容"""
        text = text.strip()
        
        if not text:
            # 无文字 -> 隐藏弹窗（不干扰，想看历史请双击）
            if self.popup.isVisible():
                self.popup.hide()
            return

        # 有文字 -> 仅在弹窗已显示时更新过滤
        # （不主动弹出，避免输入干扰）
        if self.popup.isVisible():
            self.popup.filter_ui(text)
            self.input_widget.set_focus()

    def _position_popup(self):
        """定位弹窗到输入组件正下方 (考虑阴影边距)"""
        if not self.isVisible(): return
        # 补偿 10px 的阴影外边距，确保内容对齐输入框
        pos = self.input_widget.mapToGlobal(QPoint(-10, self.input_widget.height() - 8))
        self.popup.resize(self.input_widget.width() + 20, 320) # 增加宽度和高度以容纳阴影
        self.popup.move(pos)
        self.popup.raise_()
    def _on_popup_tag_toggle(self, tag_name, checked):
        """
        勾选历史标签 -> 放入暂存区（不提交）
        """
        if checked:
            self.input_widget.add_chip(tag_name)
        else:
            # 取消勾选 -> 移除暂存
            for chip in self.input_widget.chips:
                if chip.text() == tag_name:
                    self.input_widget.remove_chip(chip)
                    break
        self.input_widget.set_focus()

    def _on_create_new_tag(self, tag_name):
        """点击新词 -> 放入暂存区（不提交）"""
        self.input_widget.add_chip(tag_name)
        self.input_widget.clear_text()
        self.input_widget.set_focus()
        self.popup.hide()

    def _on_chips_updated(self, tags):
        """暂存区变动 -> 刷新弹窗内容并动态重定位"""
        if self.popup.isVisible():
            self.popup.load_history(self.cached_tags, tags)
            # 关键：当标签增减导致输入框高度变化时，必须重新计算弹窗位置，防止遮挡
            QTimer.singleShot(10, self._position_popup) 

    def _on_tags_committed(self, tags):
        """
        回车 -> 最终提交到数据库
        """
        if tags:
            self.tags_committed.emit(tags)
        self.popup.hide()

    def load_tags(self, tags):
        """加载历史标签列表"""
        self.cached_tags = tags

    def refresh_tags(self, db_manager):
        """从数据库刷新标签"""
        try:
            stats = db_manager.get_stats()
            self.load_tags(stats.get('tags', []))
        except:
            pass