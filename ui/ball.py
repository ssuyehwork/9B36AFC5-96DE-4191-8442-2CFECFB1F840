# -*- coding: utf-8 -*-
# ui/ball.py
import math
import random
from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, 
                         QLinearGradient, QPainterPath, QPolygonF)
from core.settings import save_setting

class FloatingBall(QWidget):
    request_show_quick_window = pyqtSignal()
    request_show_main_window = pyqtSignal()
    request_quit_app = pyqtSignal()
    double_clicked = pyqtSignal()

    # --- 皮肤枚举 ---
    SKIN_MOCHA = 0   
    SKIN_CLASSIC = 1 
    SKIN_ROYAL = 2   
    SKIN_MATCHA = 3  
    SKIN_OPEN = 4    

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(130, 130) # 加大画布以容纳完整的笔迹
        self.setAcceptDrops(True)

        self.dragging = False
        self.is_hovering = False 
        
        # --- 状态与配置 ---
        self.current_skin = self.SKIN_MOCHA 
        self.is_writing = False 
        self.write_timer = 0     
        self.offset = QPoint()
        
        # --- 动画物理量 ---
        self.time_step = 0.0
        self.pen_x = 0.0
        self.pen_y = 0.0
        self.pen_angle = -45.0 
        self.book_y = 0.0
        
        # --- 墨迹系统 (核心新增) ---
        self.trail_points = [] # 存储笔尖轨迹点
        self.particles = [] 

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)
        self.timer.start(16) # ~60 FPS

    def trigger_clipboard_feedback(self):
        """触发记录成功特效"""
        self.is_writing = True
        self.write_timer = 0

    def switch_skin(self, skin_id):
        self.current_skin = skin_id
        self.update()

    def _update_physics(self):
        self.time_step += 0.05
        
        # 1. 待机悬浮 (Breathing)
        idle_pen_y = math.sin(self.time_step * 0.5) * 4
        idle_book_y = math.sin(self.time_step * 0.5 - 1.0) * 2
        
        target_pen_angle = -45
        target_pen_x = 0
        target_pen_y = idle_pen_y
        
        # 2. 书写动画 (Right-hand Scribble)
        if self.is_writing or self.is_hovering:
            self.write_timer += 1
            
            # A. 姿态：右手握笔通常稍微向右倾斜 (-55度左右)
            target_pen_angle = -55 
            
            # B. 轨迹：模拟连笔字 (Signature Wave)
            # 频率加快，幅度适中，模拟真实的快速书写
            write_speed = self.time_step * 5.0 
            
            # X轴：左右扫动 (像写一排字)
            flow_x = math.sin(write_speed) * 10
            # Y轴：上下起伏 (笔画结构) + 整体稍微下压
            flow_y = math.cos(write_speed * 2) * 3 
            
            target_pen_x = flow_x
            target_pen_y = 10 + flow_y # 笔尖贴近纸面
            idle_book_y = -3 

            # C. 记录墨迹点 (Ink Trail Logic)
            # 计算笔尖在全局坐标系中的位置
            # 笔的中心(旋转点)在: cx + pen_x, cy + pen_y - 15
            # 笔尖距离中心约为 38px (半长 + 笔尖长)
            cx, cy = self.width()/2, self.height()/2
            pivot_x = cx + self.pen_x
            pivot_y = cy + self.pen_y - 15
            
            rad = math.radians(self.pen_angle)
            tip_length = 38 
            
            # 旋转向量公式
            tip_x = pivot_x - math.sin(rad) * tip_length
            tip_y = pivot_y + math.cos(rad) * tip_length
            
            # 添加轨迹点 (x, y, opacity)
            self.trail_points.append([tip_x, tip_y, 1.0])

            if self.is_writing and self.write_timer > 90: 
                self.is_writing = False
        
        # 3. 物理平滑
        easing = 0.15 # 稍微加快响应速度，让书写更跟手
        self.pen_angle += (target_pen_angle - self.pen_angle) * easing
        self.pen_x += (target_pen_x - self.pen_x) * easing
        self.pen_y += (target_pen_y - self.pen_y) * easing
        self.book_y += (idle_book_y - self.book_y) * easing

        # 4. 墨迹与粒子淡出更新
        self._update_trails_and_particles()
        self.update()

    def _update_trails_and_particles(self):
        # A. 更新轨迹 (Fade out ink)
        alive_trail = []
        for pt in self.trail_points:
            pt[2] -= 0.04 # 墨水干得比较快
            if pt[2] > 0:
                alive_trail.append(pt)
        self.trail_points = alive_trail
        
        # B. 更新粒子 (Gold Dust / Ink Splatter)
        if (self.is_writing or self.is_hovering) and len(self.particles) < 10:
            if random.random() < 0.2:
                # 从最新轨迹点生成粒子
                if self.trail_points:
                    last_pt = self.trail_points[-1]
                    self.particles.append({
                        'x': last_pt[0],
                        'y': last_pt[1],
                        'vx': random.uniform(-0.5, 0.5),
                        'vy': random.uniform(-0.5, 0.5),
                        'life': 1.0,
                        'size': random.uniform(1, 2)
                    })

        alive_particles = []
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.05
            if p['life'] > 0:
                alive_particles.append(p)
        self.particles = alive_particles

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        
        # --- 1. 绘制阴影 ---
        p.save()
        p.translate(cx, cy + self.book_y + 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(-35, -10, 70, 20))
        p.restore()

        # --- 2. 绘制笔记本 ---
        p.save()
        p.translate(cx, cy + self.book_y)
        if self.current_skin != self.SKIN_OPEN:
            p.rotate(-6)
            
        if self.current_skin == self.SKIN_MOCHA: self._draw_book_mocha(p)
        elif self.current_skin == self.SKIN_CLASSIC: self._draw_book_classic(p)
        elif self.current_skin == self.SKIN_ROYAL: self._draw_book_royal(p)
        elif self.current_skin == self.SKIN_MATCHA: self._draw_book_matcha(p)
        elif self.current_skin == self.SKIN_OPEN: self._draw_book_open(p)
        
        # === 3. 绘制墨水轨迹 (Ink Trail) - 在书本之上，笔之下 ===
        # 根据皮肤选择墨水颜色
        ink_color = QColor(20, 20, 30) # 默认黑墨水
        if self.current_skin == self.SKIN_ROYAL: ink_color = QColor(25, 25, 112) # 蓝墨水
        elif self.current_skin == self.SKIN_MOCHA: ink_color = QColor(60, 30, 20) # 褐墨水
        
        if len(self.trail_points) > 1:
            path = QPainterPath()
            path.moveTo(QPointF(self.trail_points[0][0], self.trail_points[0][1]))
            # 使用二次贝塞尔曲线连接点，使线条平滑
            for i in range(1, len(self.trail_points) - 1):
                # 取中点作为控制点
                p1 = self.trail_points[i]
                p2 = self.trail_points[i+1]
                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
                path.quadTo(p1[0], p1[1], mid_x, mid_y)
            
            # 绘制不同透明度的轨迹 (模拟渐隐)
            # 这里为了性能和效果，我们简单绘制一条路径，透明度取中间值
            # 更完美的方法是分段绘制，但对于小图标，一条半透明线足矣
            pen_ink = QPen(ink_color)
            pen_ink.setWidthF(1.8)
            pen_ink.setCapStyle(Qt.RoundCap)
            # 整体透明度随最早的点衰减
            opacity = int(255 * 0.8) 
            if self.trail_points:
                opacity = int(255 * max(0.2, self.trail_points[0][2]))
            
            ink_color.setAlpha(opacity)
            pen_ink.setColor(ink_color)
            
            # 坐标系已经在translate(cx, cy+book_y)里了? 
            # 不，trail_points 记录的是全局坐标。
            # 我们需要临时恢复坐标系来画线，或者逆变换。
            # 简单做法：restore后在画笔前画线。
            p.restore() # 恢复到 (0,0)
            
            p.setPen(pen_ink)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        else:
            p.restore() # 没轨迹也要恢复

        # --- 4. 绘制笔的投影 ---
        p.save()
        # 投影在纸上，跟随笔的XY，但稍微滞后
        p.translate(cx + self.pen_x + 6, cy + self.book_y - 2 + self.pen_y * 0.6) 
        p.rotate(self.pen_angle)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(40, 30, 20, 50)) 
        p.drawRoundedRect(QRectF(-4, -15, 8, 40), 4, 4)
        p.restore()

        # --- 5. 绘制钢笔 ---
        p.save()
        # 笔的旋转中心
        p.translate(cx + self.pen_x, cy + self.pen_y - 15)
        p.rotate(self.pen_angle)
        self._draw_universal_pen(p)
        p.restore()
        
        # --- 6. 绘制粒子 ---
        for pt in self.particles:
            c = QColor(255, 215, 0, int(255 * pt['life'])) # 金粉
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QRectF(pt['x']-pt['size']/2, pt['y']-pt['size']/2, pt['size'], pt['size']))

    # ... (Drawing Helper Functions remain largely the same, optimized for looks) ...
    def _draw_universal_pen(self, p):
        """一支高质感钢笔"""
        w_pen, h_pen = 12, 46
        # 颜色适配
        if self.current_skin == self.SKIN_ROYAL:
            c1, c2, c3 = QColor(60, 60, 70), QColor(20, 20, 25), QColor(0, 0, 0)
        elif self.current_skin == self.SKIN_MATCHA:
            c1, c2, c3 = QColor(255, 255, 250), QColor(240, 240, 230), QColor(200, 200, 190)
        elif self.current_skin == self.SKIN_CLASSIC:
            c1, c2, c3 = QColor(80, 80, 80), QColor(30, 30, 30), QColor(10, 10, 10)
        else: # Mocha
            c1, c2, c3 = QColor(180, 60, 70), QColor(140, 20, 30), QColor(60, 5, 10)

        body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
        body_grad.setColorAt(0.0, c1); body_grad.setColorAt(0.5, c2); body_grad.setColorAt(1.0, c3) 

        path_body = QPainterPath()
        path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 5, 5)
        p.setPen(Qt.NoPen); p.setBrush(body_grad); p.drawPath(path_body)
        
        # 笔尖
        path_tip = QPainterPath()
        tip_h = 14
        path_tip.moveTo(-w_pen/2 + 3, h_pen/2); path_tip.lineTo(w_pen/2 - 3, h_pen/2); path_tip.lineTo(0, h_pen/2 + tip_h); path_tip.closeSubpath()
        tip_grad = QLinearGradient(-5, 0, 5, 0)
        tip_grad.setColorAt(0, QColor(240, 230, 180)); tip_grad.setColorAt(1, QColor(190, 170, 100)) 
        p.setBrush(tip_grad); p.drawPath(path_tip)
        
        # 细节
        p.setBrush(QColor(220, 200, 140)); p.drawRect(QRectF(-w_pen/2, h_pen/2 - 4, w_pen, 4))
        p.setBrush(QColor(210, 190, 130)); p.drawRoundedRect(QRectF(-1.5, -h_pen/2 + 6, 3, 24), 1.5, 1.5)

    def _draw_book_mocha(self, p):
        w, h = 56, 76
        p.setBrush(QColor(245, 240, 225)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50)); grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(120, 20, 30)); p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))

    def _draw_book_classic(self, p):
        w, h = 54, 74
        p.setBrush(QColor(235, 235, 230)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(60, 60, 65)); grad.setColorAt(1, QColor(20, 20, 25))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(10, 10, 10, 200)); p.drawRect(QRectF(w/2 - 12, -h/2, 6, h))

    def _draw_book_royal(self, p):
        w, h = 58, 76
        p.setBrush(QColor(240, 240, 235)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 2, 2)
        grad = QLinearGradient(-w, -h, w, 0)
        grad.setColorAt(0, QColor(40, 40, 100)); grad.setColorAt(1, QColor(10, 10, 50))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 2, 2)
        p.setBrush(QColor(218, 165, 32)); c=12; p.drawPolygon(QPolygonF([QPoint(int(w/2), int(-h/2)), QPoint(int(w/2-c), int(-h/2)), QPoint(int(w/2), int(-h/2+c))]))

    def _draw_book_matcha(self, p):
        w, h = 54, 74
        p.setBrush(QColor(250, 250, 245)); p.drawRoundedRect(QRectF(-w/2+5, -h/2+5, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(160, 190, 150)); grad.setColorAt(1, QColor(100, 130, 90))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(255, 255, 255, 200)); p.drawRoundedRect(QRectF(-w/2+10, -20, 34, 15), 2, 2)

    def _draw_book_open(self, p):
        w, h = 80, 50
        p.rotate(-5)
        path = QPainterPath(); path.moveTo(-w/2, -h/2); path.lineTo(0, -h/2 + 4); path.lineTo(w/2, -h/2); path.lineTo(w/2, h/2); path.lineTo(0, h/2 + 4); path.lineTo(-w/2, h/2); path.closeSubpath()
        p.setBrush(QColor(248, 248, 245)); p.setPen(Qt.NoPen); p.drawPath(path)
        grad = QLinearGradient(-10, 0, 10, 0); grad.setColorAt(0, QColor(0,0,0,0)); grad.setColorAt(0.5, QColor(0,0,0,20)); grad.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(grad); p.drawRect(QRectF(-5, -h/2+4, 10, h-4))
        p.setPen(QPen(QColor(200, 200, 200), 1))
        for y in range(int(-h/2)+15, int(h/2), 7):
            p.drawLine(int(-w/2+5), y, -5, y+2); p.drawLine(5, y+2, int(w/2-5), y)

    # --- 交互 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasText(): e.accept(); self.is_hovering = True
        else: e.ignore()
    def dragLeaveEvent(self, e): self.is_hovering = False
    def dropEvent(self, e):
        self.is_hovering = False
        text = e.mimeData().text()
        if text.strip(): self.mw.quick_add_idea(text); self.trigger_clipboard_feedback(); e.acceptProposedAction()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.dragging = True; self.offset = e.pos(); self.pen_y += 3
    def mouseMoveEvent(self, e):
        if self.dragging: self.move(self.mapToGlobal(e.pos() - self.offset))
    def mouseReleaseEvent(self, e):
        if self.dragging: self.dragging = False; pos = self.pos(); save_setting('floating_ball_pos', {'x': pos.x(), 'y': pos.y()})
    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton: self.double_clicked.emit()
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet("QMenu { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #444; border-radius: 5px; } QMenu::item { padding: 6px 25px; } QMenu::item:selected { background-color: #5D4037; color: #fff; } QMenu::separator { background-color: #444; height: 1px; margin: 4px 0; }")
        sm = m.addMenu("🎨  切换外观")
        sm.addAction("☕  摩卡·勃艮第", lambda: self.switch_skin(self.SKIN_MOCHA))
        sm.addAction("♟️  经典黑金", lambda: self.switch_skin(self.SKIN_CLASSIC))
        sm.addAction("📘  皇家蓝", lambda: self.switch_skin(self.SKIN_ROYAL))
        sm.addAction("🍵  抹茶绿", lambda: self.switch_skin(self.SKIN_MATCHA))
        sm.addAction("📖  摊开手稿", lambda: self.switch_skin(self.SKIN_OPEN))
        m.addSeparator()
        m.addAction('⚡ 打开快速笔记', self.request_show_quick_window.emit)
        m.addAction('💻 打开主界面', self.request_show_main_window.emit)
        m.addAction('➕ 新建灵感', self.mw.new_idea)
        m.addSeparator()
        m.addAction('❌ 退出', self.request_quit_app.emit)
        m.exec_(e.globalPos())