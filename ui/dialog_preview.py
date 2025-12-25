# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QFrame, 
                             QSizePolicy, QScrollArea, QPushButton, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QPoint, QTimer, QSize
from PyQt5.QtGui import QPixmap, QCursor, QTransform, QColor

class PreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.resize(1000, 750)
        
        self.current_scale = 1.0
        self.original_pixmap = None
        self.rotation_angle = 0
        self.is_dragging = False
        self.last_mouse_pos = QPoint()
        self.mode = 'image'

        # 初始化窗口拖动所需的变量
        self.is_window_dragging = False
        self.drag_start_position = QPoint()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(0)
        
        self.container = QFrame()
        self.container.setObjectName("PreviewContainer")
        self.container.setStyleSheet("""
            #PreviewContainer {
                background-color: #2b2b2b;
                border: 1px solid #454545;
                border-radius: 8px;
            }
        """)
        
        # Window Shadow
        window_shadow = QGraphicsDropShadowEffect(self)
        window_shadow.setBlurRadius(50)
        window_shadow.setXOffset(0)
        window_shadow.setYOffset(0)
        window_shadow.setColor(QColor(0, 0, 0, 180))
        self.container.setGraphicsEffect(window_shadow)
        
        self.layout.addWidget(self.container)
        
        self.inner_layout = QVBoxLayout(self.container)
        self.inner_layout.setContentsMargins(2, 2, 2, 2)
        self.inner_layout.setSpacing(0)
        
        self.top_bar = QFrame() 
        self.top_layout = QHBoxLayout(self.top_bar)
        self.top_layout.setContentsMargins(15, 5, 15, 5)
        
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("PreviewInfoLabel")
        self.top_layout.addWidget(self.lbl_info)
        self.top_layout.addStretch()
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_close.setObjectName("PreviewDialogCloseButton")
        self.top_layout.addWidget(btn_close)
        
        self.inner_layout.addWidget(self.top_bar)
        
        self.content_area = QFrame()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 图片预览容器 (为了容纳阴影，不被 ScrollArea 截断)
        self.image_container = QWidget()
        self.image_container_layout = QVBoxLayout(self.image_container)
        self.image_container_layout.setContentsMargins(40, 40, 40, 40) # 宽大的阴影呼吸空间
        self.image_container_layout.setAlignment(Qt.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setObjectName("PreviewImage")
        
        # 注入强物理阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 200))
        self.image_label.setGraphicsEffect(shadow)
        
        self.image_container_layout.addWidget(self.image_label)
        self.scroll_area.setWidget(self.image_container)
        
        self.content_layout.addWidget(self.scroll_area)
        
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setObjectName("PreviewTextEdit")
        self.content_layout.addWidget(self.text_preview)
        
        self.inner_layout.addWidget(self.content_area, 1)

        self.controls = QFrame()
        self.controls.setFixedHeight(50)
        self.controls.setObjectName("PreviewControls")
        
        ctrl_layout = QHBoxLayout(self.controls)
        ctrl_layout.setContentsMargins(0, 5, 0, 10)
        ctrl_layout.setAlignment(Qt.AlignCenter)
        
        self.btn_zoom_out = self._create_control_button("－", "缩小 (-)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        
        self.btn_100 = self._create_control_button("1:1", "原始尺寸 (1)")
        self.btn_100.clicked.connect(self.reset_zoom)
        
        self.btn_fit = self._create_control_button("Fit", "适应窗口 (0)")
        self.btn_fit.clicked.connect(self.fit_to_window)
        
        self.btn_zoom_in = self._create_control_button("＋", "放大 (+)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        
        self.btn_rot_l = self._create_control_button("↺", "左旋转 (L)")
        self.btn_rot_l.clicked.connect(lambda: self.rotate(-90))
        
        self.btn_rot_r = self._create_control_button("↻", "右旋转 (R)")
        self.btn_rot_r.clicked.connect(lambda: self.rotate(90))

        ctrl_layout.addWidget(self.btn_rot_l)
        ctrl_layout.addWidget(self.btn_zoom_out)
        ctrl_layout.addWidget(self.btn_100)
        ctrl_layout.addWidget(self.btn_fit)
        ctrl_layout.addWidget(self.btn_zoom_in)
        ctrl_layout.addWidget(self.btn_rot_r)
        
        self.inner_layout.addWidget(self.controls)
        
        self.text_preview.installEventFilter(self)
        self.image_label.installEventFilter(self)
        self.image_container.installEventFilter(self)
        self.scroll_area.installEventFilter(self)

    def _create_control_button(self, text, tooltip):
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setObjectName("PreviewControlButton")
        btn.setFocusPolicy(Qt.NoFocus)
        return btn

    def eventFilter(self, source, event):
        if event.type() == event.KeyPress:
            if event.key() in [Qt.Key_Space, Qt.Key_Escape]:
                self.close()
                return True
            if event.key() in [Qt.Key_Plus, Qt.Key_Equal]:
                self.zoom_in(); return True
            if event.key() == Qt.Key_Minus:
                self.zoom_out(); return True
            if event.key() == Qt.Key_0:
                self.fit_to_window(); return True
            if event.key() == Qt.Key_1:
                self.reset_zoom(); return True
            if event.key() == Qt.Key_R:
                self.rotate(90); return True
            if event.key() == Qt.Key_L:
                self.rotate(-90); return True

        if source in [self.image_label, self.image_container] and self.mode == 'image':
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                self.is_dragging = True
                self.last_mouse_pos = event.globalPos()
                self.setCursor(Qt.ClosedHandCursor)
                return True
            elif event.type() == event.MouseMove and self.is_dragging:
                delta = event.globalPos() - self.last_mouse_pos
                self.last_mouse_pos = event.globalPos()
                h = self.scroll_area.horizontalScrollBar()
                v = self.scroll_area.verticalScrollBar()
                h.setValue(h.value() - delta.x())
                v.setValue(v.value() - delta.y())
                return True
            elif event.type() == event.MouseButtonRelease:
                self.is_dragging = False
                self.update_cursor()
                return True

        if event.type() == event.Wheel and source == self.text_preview:
             if event.modifiers() == Qt.ControlModifier:
                 delta = event.angleDelta().y()
                 if delta > 0: self.text_preview.zoomIn(1)
                 else: self.text_preview.zoomOut(1)
                 return True

        return super().eventFilter(source, event)

    def load_data(self, content, item_type, file_path=None, image_path=None, image_blob=None):
        self.clear_state()
        
        pixmap = QPixmap()
        can_show_image = False

        if item_type == 'image':
            if image_blob:
                can_show_image = pixmap.loadFromData(image_blob)
            else: # 兼容旧数据
                import os
                path_to_try = image_path or file_path
                if path_to_try and os.path.exists(path_to_try):
                    can_show_image = pixmap.load(path_to_try)

        if can_show_image:
            self.mode = 'image'
            self.original_pixmap = pixmap
            self.scroll_area.show()
            self.controls.show()
            self.fit_to_window(fast_mode=True)
            self.update_info_label()
            self.scroll_area.setFocus()
            return

        self.mode = 'text'
        self.text_preview.setPlainText(content)
        self.text_preview.show()
        self.controls.hide() 
        f = self.text_preview.font()
        f.setPointSize(14)
        self.text_preview.setFont(f)
        self.lbl_info.setText("Text View")

    def clear_state(self):
        self.image_label.clear()
        self.image_container.adjustSize()
        self.text_preview.clear()
        self.scroll_area.hide()
        self.text_preview.hide()
        self.current_scale = 1.0
        self.rotation_angle = 0
        self.original_pixmap = None
        self.is_dragging = False
        self.setCursor(Qt.ArrowCursor)

    def update_image_display(self, fast_mode=False):
        if not self.original_pixmap: return
        
        transform = QTransform().rotate(self.rotation_angle)
        processed_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        
        if self.current_scale <= 0: self.current_scale = 0.1
        
        target_w = min(int(processed_pixmap.width() * self.current_scale), 10000)
        target_h = min(int(processed_pixmap.height() * self.current_scale), 10000)
        
        mode = Qt.FastTransformation if fast_mode or (processed_pixmap.width() > 3000 and self.current_scale < 1.0) else Qt.SmoothTransformation

        final = processed_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, mode)
        self.image_label.setPixmap(final)
        self.image_label.setFixedSize(final.size()) # 锁定标签尺寸，防止抖动
        self.image_container.adjustSize() # 驱动容器重新计算阴影边距
        
        self.update_cursor()
        self.update_info_label(processed_pixmap.width(), processed_pixmap.height())

    def update_cursor(self):
        if self.mode == 'image' and (self.current_scale > 1.0 or self.image_label.width() > self.scroll_area.width() or self.image_label.height() > self.scroll_area.height()):
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def update_info_label(self, w=0, h=0):
        if self.mode == 'image':
            if w == 0 and self.original_pixmap:
                w, h = self.original_pixmap.width(), self.original_pixmap.height()
            self.lbl_info.setText(f"{w}x{h} | {int(self.current_scale*100)}% | {self.rotation_angle}°")
        else:
            self.lbl_info.setText("Text View")

    def zoom_in(self):
        if self.mode == 'image': self.current_scale *= 1.2; self.update_image_display()
        else: self.text_preview.zoomIn(1)

    def zoom_out(self):
        if self.mode == 'image': self.current_scale /= 1.2; self.update_image_display()
        else: self.text_preview.zoomOut(1)

    def reset_zoom(self):
        self.current_scale = 1.0
        self.rotation_angle = 0
        self.update_image_display()
    
    def fit_to_window(self, fast_mode=False):
        if not self.original_pixmap: return
        self.rotation_angle = 0
        
        view_w = self.scroll_area.width() - 10
        view_h = self.scroll_area.height() - 10
        
        scale_w = view_w / self.original_pixmap.width()
        scale_h = view_h / self.original_pixmap.height()
        self.current_scale = min(scale_w, scale_h, 1.0)
        
        self.update_image_display(fast_mode=fast_mode)

    def rotate(self, angle):
        self.rotation_angle = (self.rotation_angle + angle) % 360
        self.update_image_display()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.mode == 'image':
            if delta > 0: self.zoom_in()
            else: self.zoom_out()
        elif event.modifiers() == Qt.ControlModifier:
            if delta > 0: self.zoom_in()
            else: self.zoom_out()
        else:
            super().wheelEvent(event)

    def closeEvent(self, event):
        self.clear_state()
        super().closeEvent(event)

    # === 窗口拖动逻辑 ===
    def mousePressEvent(self, event):
        # 检查是否在标题栏上按下左键
        if event.button() == Qt.LeftButton and self.top_bar.geometry().contains(event.pos()):
            self.is_window_dragging = True
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_window_dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.is_window_dragging = False
        event.accept()
