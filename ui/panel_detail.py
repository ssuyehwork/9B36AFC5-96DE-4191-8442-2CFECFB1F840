# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, 
                             QLineEdit, QPushButton, QScrollArea, QFrame, QSizePolicy, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QMouseEvent, QColor
import os
from .flow_layout import FlowLayout  # 导入新的布局管理器
from .widgets.tag_widget import TagWidget


class DetailPanel(QWidget):
    update_note_signal = pyqtSignal(str)
    tags_added_signal = pyqtSignal(list) # 新的信号，用于提交标签列表
    remove_tag_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
            
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 12) # 缩减内边距，把空间还给文字
        self.layout.setSpacing(12) 
        
        # 0. 所属分区/分组信息
        partition_info_layout = QHBoxLayout()
        self.lbl_group = QLabel("分组: --")
        self.lbl_group.setObjectName("PartitionInfoLabel")
        self.lbl_partition = QLabel("分区: --")
        self.lbl_partition.setObjectName("PartitionInfoLabel")
        partition_info_layout.addWidget(self.lbl_group)
        partition_info_layout.addSpacing(20)
        partition_info_layout.addWidget(self.lbl_partition)
        partition_info_layout.addStretch()
        self.layout.addLayout(partition_info_layout)

        # 1. 内容预览模块
        # 文本预览组件
        self.preview = QTextEdit()
        self.preview.setObjectName("PreviewBox")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("暂无内容...")
        self.preview.textChanged.connect(self._update_preview_height) # 文本变化时更新高度
        self.layout.addWidget(self.preview)
        
        # 图片预览组件容器 (用于承载阴影)
        self.image_container = QWidget()
        self.image_container_layout = QVBoxLayout(self.image_container)
        self.image_container_layout.setContentsMargins(10, 10, 10, 10) # 预留阴影显示空间
        self.image_container_layout.setAlignment(Qt.AlignCenter) # 关键：确保内部组件居中
        
        self.image_label = QLabel()
        self.image_label.setObjectName("ImageBox")
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # 为图片增加物理阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.image_label.setGraphicsEffect(shadow)
        
        self.image_container_layout.addWidget(self.image_label)
        self.image_container.hide()
        self.layout.addWidget(self.image_container)

        # 2. 备注模块
        note_container = QWidget()
        note_layout = QVBoxLayout(note_container)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.setSpacing(4)
        
        lbl_note = QLabel("备注:")
        lbl_note.setObjectName("SectionTitle")
        note_layout.addWidget(lbl_note)
        
        self.note_edit = QLineEdit()
        self.note_edit.setObjectName("NoteInput")
        self.note_edit.setPlaceholderText("点击添加备注信息...")
        self.note_edit.setEnabled(False) # 默认禁用
        self.note_edit.returnPressed.connect(lambda: self.update_note_signal.emit(self.note_edit.text()))
        note_layout.addWidget(self.note_edit)
        
        self.layout.addWidget(note_container)
        
        # 3. 标签模块
        tag_container_widget = QWidget()
        tag_main_layout = QVBoxLayout(tag_container_widget)
        tag_main_layout.setContentsMargins(0, 0, 0, 0)
        tag_main_layout.setSpacing(8)
        
        # 标签头
        header_line = QHBoxLayout()
        lbl_tags = QLabel("标签:")
        lbl_tags.setObjectName("SectionTitle")
        header_line.addWidget(lbl_tags)
        header_line.addStretch()
        tag_main_layout.addLayout(header_line)
        
        # 标签流式区域 (替换为 FlowLayout)
        self.tag_content = QWidget()
        self.tag_content.setObjectName("TagContainer")
        self.tag_layout = FlowLayout(self.tag_content, spacing=6) # 使用新的布局
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        
        tag_main_layout.addWidget(self.tag_content)
        
        self.layout.addWidget(tag_container_widget)

        # 新增：标签输入框（移动到主布局的末尾）
        self.tag_input = QLineEdit()
        self.tag_input.setObjectName("NoteInput") # 复用备注输入框的样式
        self.tag_input.setPlaceholderText("输入标签，用逗号分隔...")
        self.tag_input.returnPressed.connect(self._on_tags_submitted)
        self.tag_input.setEnabled(False) # 默认禁用

        # 添加一个弹簧，将所有内容推到顶部
        self.layout.addStretch(1)
        self.layout.addWidget(self.tag_input)

    def load_item(self, content, note, tags, group_name=None, partition_name=None, item_type='text', image_path=None, file_path=None, image_blob=None):
        # 设置分区信息
        self.lbl_group.setText(f"分组: {group_name or '--'}")
        self.lbl_partition.setText(f"分区: {partition_name or '未分类'}")

        # 设置备注
        self.note_edit.setText(note)
        self.note_edit.setCursorPosition(0)
        
        pixmap = QPixmap()
        can_show_image = False

        if item_type == 'image':
            if image_blob:
                can_show_image = pixmap.loadFromData(image_blob)
            else: # 兼容旧数据
                path_to_try = image_path or file_path
                if path_to_try and os.path.exists(path_to_try):
                    can_show_image = pixmap.load(path_to_try)

        if can_show_image:
            self.preview.hide()
            self.image_container.show()
            self.image_label.show()
            max_w = self.width() - 40
            scaled_pixmap = pixmap.scaled(max_w, max_w, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setFixedSize(scaled_pixmap.size())
        else:
            self.image_container.hide()
            self.image_label.hide()
            self.preview.show()
            self.preview.setText(content)

        # 加载数据后，启用交互组件
        self.note_edit.setEnabled(True)
        self.tag_input.setEnabled(True)
        
        # 刷新标签和高度
        self._refresh_tags(tags)
        self._update_preview_height()

    def _update_preview_height(self):
        """智能计算并设置预览框的高度"""
        # 仅在文本预览可见时操作
        if self.preview.isVisible():
            # 获取文档的实际高度
            doc_height = self.preview.document().size().height()
            
            # 获取边距 (approax.)
            margins = self.preview.contentsMargins()
            # 额外增加5像素的缓冲空间，避免因细微计算误差导致不必要的滚动条出现
            content_height = doc_height + margins.top() + margins.bottom() + 5
            
            # 最大高度不能超过宽度
            max_h = self.preview.width()
            
            # 设置固定高度
            final_height = min(content_height, max_h)
            self.preview.setFixedHeight(int(final_height))

    def _refresh_tags(self, tags):
        # 清空旧标签
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            
        if not tags:
            lbl_empty = QLabel("无标签")
            lbl_empty.setObjectName("EmptyTagLabel")
            self.tag_layout.addWidget(lbl_empty)
            return

        for tag_name in tags:
            tag_widget = TagWidget(tag_name)
            tag_widget.removed.connect(self.remove_tag_signal.emit)
            self.tag_layout.addWidget(tag_widget)

    def clear(self):
        self.lbl_group.setText("分组: --")
        self.lbl_partition.setText("分区: --")
        self.preview.clear()
        self.note_edit.clear()
        
        # 清空数据时，禁用交互组件
        self.note_edit.setEnabled(False)
        self.tag_input.setEnabled(False)
        
        self._refresh_tags([])
        self.image_container.hide()
        self.image_label.hide()
        self.preview.show()

    def resizeEvent(self, event):
        """重写 resize 事件，以便在面板宽度变化时更新预览高度"""
        super().resizeEvent(event)
        self._update_preview_height()

    def _on_tags_submitted(self):
        """处理标签输入框的回车事件"""
        text = self.tag_input.text().strip()
        if text:
            # 同时支持中英文逗号分割
            tags = [tag.strip() for tag in text.replace('，', ',').split(',') if tag.strip()]
            if tags:
                self.tags_added_signal.emit(tags)
            self.tag_input.clear()