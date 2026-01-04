# -*- coding: utf-8 -*-
# ui/ball.py
import math
import random
from PyQt5.QtWidgets import QWidget, QMenu, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QRectF
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, 
                         QLinearGradient, QPainterPath, QPolygonF)
from core.settings import save_setting, load_setting

class FloatingBall(QWidget):
    request_show_quick_window = pyqtSignal()
    request_show_main_window = pyqtSignal()
    request_quit_app = pyqtSignal()
    double_clicked = pyqtSignal()
    request_show_tag_manager = pyqtSignal()

    # --- 皮肤枚举 ---
    SKIN_MOCHA = 0   # 摩卡·勃艮第 (最新款)
    SKIN_CLASSIC = 1 # 经典黑金 (商务风)
    SKIN_ROYAL = 2   # 皇家蓝 (学术风)
    SKIN_MATCHA = 3  # 抹茶绿 (清新风) - 新增
    SKIN_OPEN = 4    # 摊开手稿 (沉浸风)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(120, 120) # 尺寸加大适配各种款式
        self.setAcceptDrops(True)

        self.dragging = False
        self.is_hovering = False 
        
        # --- 状态与配置 ---
        self.current_skin = load_setting('floating_ball_skin', self.SKIN_MOCHA)
        self.is_writing = False 
        self.write_timer = 0     
        self.offset = QPoint()
        
        # --- 动画物理量 ---
        self.time_step = 0.0
        self.pen_x = 0.0
        self.pen_y = 0.0
        self.pen_angle = -45.0 
        self.book_y = 0.0
        
        # 粒子
        self.particles = [] 

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)
        self.timer.start(16)

        self._restore_position()

    def _restore_position(self):
        """恢复悬浮球的位置"""
        pos_data = load_setting('floating_ball_pos')
        if isinstance(pos_data, dict) and 'x' in pos_data and 'y' in pos_data:
            self.move(QPoint(pos_data['x'], pos_data['y']))
        else:
            # 默认位置：屏幕右上角
            screen_rect = QApplication.desktop().screenGeometry()
            self.move(screen_rect.width() - self.width() - 50, 100)

    def trigger_clipboard_feedback(self):
        """触发记录成功特效"""
        self.is_writing = True
        self.write_timer = 0

    def switch_skin(self, skin_id):
        """切换皮肤并刷新"""
        self.current_skin = skin_id
        save_setting('floating_ball_skin', skin_id)
        self.update()

    def _update_physics(self):
        self.time_step += 0.05
        
        # 1. 待机悬浮 (Breathing)
        # 不同的书可能有不同的悬浮重心，但动画逻辑通用
        idle_pen_y = math.sin(self.time_step * 0.5) * 4
        idle_book_y = math.sin(self.time_step * 0.5 - 1.0) * 2
        
        target_pen_angle = -45
        target_pen_x = 0
        target_pen_y = idle_pen_y
        
        # 2. 书写动画 (Fluid Signature Flow) - 适用于所有皮肤
        if self.is_writing or self.is_hovering:
            self.write_timer += 1
            
            # 笔立起来
            target_pen_angle = -65 
            
            # 流畅的连笔字轨迹 (Lissajous)
            write_speed = self.time_step * 3.0
            flow_x = math.sin(write_speed) * 8     
            flow_y = math.cos(write_speed * 2) * 2 
            
            target_pen_x = flow_x
            target_pen_y = 5 + flow_y 
            idle_book_y = -3 # 书本上浮迎接

            if self.is_writing and self.write_timer > 90: 
                self.is_writing = False
        
        # 3. 物理平滑
        easing = 0.1
        self.pen_angle += (target_pen_angle - self.pen_angle) * easing
        self.pen_x += (target_pen_x - self.pen_x) * easing
        self.pen_y += (target_pen_y - self.pen_y) * easing
        self.book_y += (idle_book_y - self.book_y) * easing

        # 4. 粒子更新
        self._update_particles()
        self.update()

    def _update_particles(self):
        # 只有在书写时产生
        if (self.is_writing or self.is_hovering) and len(self.particles) < 15:
            if random.random() < 0.3:
                rad = math.radians(self.pen_angle)
                tip_len = 35 
                
                # 根据皮肤决定粒子颜色
                is_gold = random.random() > 0.3
                self.particles.append({
                    'x': self.width()/2 + self.pen_x - math.sin(rad)*tip_len,
                    'y': self.height()/2 + self.pen_y + math.cos(rad)*tip_len,
                    'vx': random.uniform(-0.5, 0.5),
                    'vy': random.uniform(0.5, 1.5),
                    'life': 1.0,
                    'size': random.uniform(1, 3),
                    'type': 'gold' if is_gold else 'ink'
                })

        alive = []
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.03
            p['size'] *= 0.96
            if p['life'] > 0:
                alive.append(p)
        self.particles = alive

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        
        # --- 1. 绘制阴影 (通用) ---
        p.save()
        p.translate(cx, cy + self.book_y + 15)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(-35, -10, 70, 20))
        p.restore()

        # --- 2. 绘制笔记本 (根据皮肤) ---
        p.save()
        p.translate(cx, cy + self.book_y)
        # 大部分本子微倾斜，除了摊开的
        if self.current_skin != self.SKIN_OPEN:
            p.rotate(-6)
            
        if self.current_skin == self.SKIN_MOCHA:
            self._draw_book_mocha(p)
        elif self.current_skin == self.SKIN_CLASSIC:
            self._draw_book_classic(p)
        elif self.current_skin == self.SKIN_ROYAL:
            self._draw_book_royal(p)
        elif self.current_skin == self.SKIN_MATCHA:
            self._draw_book_matcha(p)
        elif self.current_skin == self.SKIN_OPEN:
            self._draw_book_open(p)
        p.restore()

        # --- 3. 绘制笔的投影 ---
        p.save()
        p.translate(cx + self.pen_x + 5, cy + self.book_y - 2 + self.pen_y * 0.5) 
        p.rotate(self.pen_angle)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(40, 30, 20, 50)) 
        p.drawRoundedRect(QRectF(-4, -15, 8, 40), 4, 4)
        p.restore()

        # --- 4. 绘制钢笔 (统一使用高质感笔模型，但可微调色相) ---
        p.save()
        p.translate(cx + self.pen_x, cy + self.pen_y - 15)
        p.rotate(self.pen_angle)
        self._draw_universal_pen(p)
        p.restore()
        
        # --- 5. 绘制粒子 ---
        for pt in self.particles:
            alpha = int(255 * pt['life'])
            if pt['type'] == 'gold':
                c = QColor(255, 215, 0, alpha)
            else:
                # 墨水颜色根据皮肤适配
                if self.current_skin == self.SKIN_ROYAL:
                    c = QColor(25, 25, 112, int(alpha*0.8)) # 蓝墨水
                else:
                    c = QColor(60, 0, 0, int(alpha*0.8)) # 红/褐墨水
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QRectF(pt['x']-pt['size']/2, pt['y']-pt['size']/2, pt['size'], pt['size']))

    # ============================================
    #              DRAWING IMPL
    # ============================================

    def _draw_universal_pen(self, p):
        """一支高精度的钢笔，颜色根据皮肤自动适配"""
        w_pen, h_pen = 12, 46
        
        # 决定笔身颜色
        if self.current_skin == self.SKIN_ROYAL:
            # 皇家蓝配黑金笔
            c_light, c_mid, c_dark = QColor(60, 60, 70), QColor(20, 20, 25), QColor(0, 0, 0)
        elif self.current_skin == self.SKIN_CLASSIC:
            # 经典款配纯黑笔
            c_light, c_mid, c_dark = QColor(80, 80, 80), QColor(30, 30, 30), QColor(10, 10, 10)
        elif self.current_skin == self.SKIN_MATCHA:
            # 抹茶配白金笔
            c_light, c_mid, c_dark = QColor(255, 255, 250), QColor(240, 240, 230), QColor(200, 200, 190)
        else:
            # 摩卡/其他配勃艮第红笔
            c_light, c_mid, c_dark = QColor(180, 60, 70), QColor(140, 20, 30), QColor(60, 5, 10)

        # 笔身渐变
        body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
        body_grad.setColorAt(0.0, c_light) 
        body_grad.setColorAt(0.5, c_mid) 
        body_grad.setColorAt(1.0, c_dark) 

        # 绘制笔身
        path_body = QPainterPath()
        path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(body_grad)
        p.drawPath(path_body)
        
        # 笔尖 (香槟金)
        path_tip = QPainterPath()
        tip_h = 14
        path_tip.moveTo(-w_pen/2 + 3, h_pen/2)
        path_tip.lineTo(w_pen/2 - 3, h_pen/2)
        path_tip.lineTo(0, h_pen/2 + tip_h)
        path_tip.closeSubpath()
        
        tip_grad = QLinearGradient(-5, 0, 5, 0)
        tip_grad.setColorAt(0, QColor(240, 230, 180)) 
        tip_grad.setColorAt(1, QColor(190, 170, 100)) 
        p.setBrush(tip_grad)
        p.drawPath(path_tip)
        
        # 装饰细节 (金环 + 笔夹)
        p.setBrush(QColor(220, 200, 140))
        p.drawRect(QRectF(-w_pen/2, h_pen/2 - 4, w_pen, 4))
        p.setBrush(QColor(210, 190, 130)) 
        p.drawRoundedRect(QRectF(-1.5, -h_pen/2 + 6, 3, 24), 1.5, 1.5)

    def _draw_book_mocha(self, p):
        """摩卡·勃艮第 (Mocha Theme)"""
        w, h = 56, 76
        # 页厚
        p.setBrush(QColor(245, 240, 225))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        # 封面渐变 (褐)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50))
        grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 红色书签带
        p.setBrush(QColor(120, 20, 30))
        p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))

    def _draw_book_classic(self, p):
        """经典黑金 (Classic Theme)"""
        w, h = 54, 74
        # 页厚 (更白一点的纸)
        p.setBrush(QColor(235, 235, 230))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        # 封面 (黑灰)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(60, 60, 65))
        grad.setColorAt(1, QColor(20, 20, 25))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 黑色弹力带
        p.setBrush(QColor(10, 10, 10, 200))
        p.drawRect(QRectF(w/2 - 12, -h/2, 6, h))

    def _draw_book_royal(self, p):
        """皇家蓝 (Royal Theme)"""
        w, h = 58, 76
        # 页厚
        p.setBrush(QColor(240, 240, 235))
        p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 2, 2)
        # 封面 (午夜蓝)
        grad = QLinearGradient(-w, -h, w, 0)
        grad.setColorAt(0, QColor(40, 40, 100))
        grad.setColorAt(1, QColor(10, 10, 50))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 2, 2)
        # 金色包角
        p.setBrush(QColor(218, 165, 32))
        c_size = 12
        p.drawPolygon(QPolygonF([QPoint(int(w/2), int(-h/2)), QPoint(int(w/2-c_size), int(-h/2)), QPoint(int(w/2), int(-h/2+c_size))]))

    def _draw_book_matcha(self, p):
        """抹茶绿 (Matcha Theme) - 浅色系"""
        w, h = 54, 74
        # 页厚
        p.setBrush(QColor(250, 250, 245))
        p.drawRoundedRect(QRectF(-w/2+5, -h/2+5, w, h), 3, 3)
        # 封面 (抹茶绿)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(160, 190, 150))
        grad.setColorAt(1, QColor(100, 130, 90))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        # 白色标签
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawRoundedRect(QRectF(-w/2+10, -20, 34, 15), 2, 2)

    def _draw_book_open(self, p):
        """摊开的手稿 (Open Theme)"""
        w, h = 80, 50
        p.rotate(-5)
        # 纸张形状
        path = QPainterPath()
        path.moveTo(-w/2, -h/2); path.lineTo(0, -h/2 + 4)
        path.lineTo(w/2, -h/2); path.lineTo(w/2, h/2)
        path.lineTo(0, h/2 + 4); path.lineTo(-w/2, h/2); path.closeSubpath()
        
        p.setBrush(QColor(248, 248, 245))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        
        # 中缝阴影
        grad = QLinearGradient(-10, 0, 10, 0)
        grad.setColorAt(0, QColor(0,0,0,0)); grad.setColorAt(0.5, QColor(0,0,0,20)); grad.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(grad)
        p.drawRect(QRectF(-5, -h/2+4, 10, h-4))
        
        # 横线
        p.setPen(QPen(QColor(200, 200, 200), 1))
        for y in range(int(-h/2)+15, int(h/2), 7):
            p.drawLine(int(-w/2+5), y, -5, y+2)
            p.drawLine(5, y+2, int(w/2-5), y)

    # --- 交互逻辑 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.accept()
            self.is_hovering = True
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.is_hovering = False

    def dropEvent(self, e):
        self.is_hovering = False
        text = e.mimeData().text()
        if text.strip():
            self.mw.quick_add_idea(text)
            self.trigger_clipboard_feedback()
            e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = e.pos()
            self.pen_y += 3

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.move(self.mapToGlobal(e.pos() - self.offset))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            pos = self.pos()
            save_setting('floating_ball_pos', {'x': pos.x(), 'y': pos.y()})

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        # 菜单样式美化
        m.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #444; border-radius: 5px; }
            QMenu::item { padding: 6px 25px; }
            QMenu::item:selected { background-color: #5D4037; color: #fff; }
            QMenu::separator { background-color: #444; height: 1px; margin: 4px 0; }
        """)
        
        # --- 皮肤切换菜单 ---
        skin_menu = m.addMenu("🎨  切换外观")
        
        a1 = skin_menu.addAction("☕  摩卡·勃艮第")
        a1.triggered.connect(lambda: self.switch_skin(self.SKIN_MOCHA))
        
        a2 = skin_menu.addAction("♟️  经典黑金")
        a2.triggered.connect(lambda: self.switch_skin(self.SKIN_CLASSIC))
        
        a3 = skin_menu.addAction("📘  皇家蓝")
        a3.triggered.connect(lambda: self.switch_skin(self.SKIN_ROYAL))

        a4 = skin_menu.addAction("🍵  抹茶绿")
        a4.triggered.connect(lambda: self.switch_skin(self.SKIN_MATCHA))

        a5 = skin_menu.addAction("📖  摊开手稿")
        a5.triggered.connect(lambda: self.switch_skin(self.SKIN_OPEN))
        
        m.addSeparator()
        m.addAction('📝  快速笔记', self.request_show_quick_window.emit)
        m.addAction('🗂️  打开主界面', self.request_show_main_window.emit)
        m.addAction('✨  新建灵感', self.mw.new_idea)
        m.addAction('🏷️  管理常用标签', self.request_show_tag_manager.emit)
        m.addSeparator()
        m.addAction('🚪  退出', self.request_quit_app.emit)
        
        m.exec_(e.globalPos())