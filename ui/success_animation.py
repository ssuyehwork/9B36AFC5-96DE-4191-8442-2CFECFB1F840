# -*- coding: utf-8 -*-
# ui/success_animation.py

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QVariantAnimation, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath

class SuccessAnimationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(24, 24)
        self._animation_progress = 0.0

        self.animation = QVariantAnimation(
            self,
            startValue=0.0,
            endValue=1.0,
            duration=400,
            valueChanged=self._on_animation_changed
        )

    def _on_animation_changed(self, value):
        self._animation_progress = value
        self.update()

    def start(self):
        self.animation.stop()
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景色透明
        painter.fillRect(self.rect(), Qt.transparent)

        # 定义勾的路径点
        w = self.width()
        h = self.height()
        p1 = QPointF(w * 0.2, h * 0.5)
        p2 = QPointF(w * 0.45, h * 0.75)
        p3 = QPointF(w * 0.8, h * 0.3)

        pen = QPen(QColor("#28a745"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        path = QPainterPath()
        path.moveTo(p1)

        # 动画分为两部分：
        # 0.0 -> 0.4: 绘制第一条线 (p1 -> p2)
        # 0.4 -> 1.0: 绘制第二条线 (p2 -> p3)

        if self._animation_progress <= 0.4:
            # 绘制第一部分的线段
            progress = self._animation_progress / 0.4
            end_point = p1 + (p2 - p1) * progress
            path.lineTo(end_point)
        else:
            # 绘制完整的第一部分
            path.lineTo(p2)
            # 绘制第二部分的线段
            progress = (self._animation_progress - 0.4) / 0.6
            end_point = p2 + (p3 - p2) * progress
            path.lineTo(end_point)

        painter.drawPath(path)
