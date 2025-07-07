#plotting_windows.py
import os
import numpy as np

from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import ( QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QHBoxLayout, QPushButton,
                             QStackedWidget, QTabWidget, QSizePolicy )

from config import SENSOR_DATA_FILE


class SingleChannelPlotWidget(QWidget):
    """单通道传感器数据绘图部件"""
    def __init__(self, channel_idx, history_size=100, parent=None):
        """
        初始化单通道绘图部件

        参数:
            channel_idx: 通道索引(0-7)
            history_size: 历史数据点数量
            parent: 父部件
        """
        super().__init__(parent)
        self.channel_idx = channel_idx  # 当前通道索引
        self.history_size = history_size # 历史数据长度
        self.data = np.zeros(history_size)# 初始化数据数组

        # 设置尺寸策略允许伸缩
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 传感器名称和颜色
        self.colors = [
            QColor(230, 25, 75),  # Red
            QColor(60, 180, 75),  # Green
            QColor(0, 130, 200),  # Blue
            QColor(245, 130, 48),  # Orange
            QColor(145, 30, 180),  # Purple
            QColor(70, 240, 240),  # Cyan
            QColor(240, 50, 230),  # Magenta
            QColor(210, 245, 60)  # Lime
        ]

        self.channel_names = [
            "传感器1",
            "传感器2",
            "传感器3",
            "传感器4",
            "传感器5",
            "传感器6",
            "传感器7",
            "传感器8"
        ]

        # 当前通道颜色
        self.channel_color = self.colors[channel_idx]

    def add_data(self, new_data):
        """
        添加新数据点

        参数:
            new_data: 包含8个传感器值的列表/数组
        """
        if len(new_data) > self.channel_idx:
            # 保留最新的history_size个数据点
            self.data[:-1] = self.data[1:]  # 左移数据
            self.data[-1] = new_data[self.channel_idx]  # 添加新数据


    def paintEvent(self, event):
        """
        绘制部件内容

        参数:
            event: 绘制事件
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)     # 启用抗锯齿

        # 0. 获取实际可用高度(为底部状态栏预留30像素)
        total_height = self.height()
        available_height = total_height - 30  # 为底部状态栏预留30像素

        # 1. 绘制标题区域 (顶部40像素)
        title_font = QFont("SimHei", 20, QFont.Bold)
        painter.setFont(title_font)

        # 绘制标题背景
        title_rect = QRect(0, 0, self.width(), 40)
        painter.fillRect(title_rect, QColor(240, 240, 240))

        # 绘制标题
        painter.setPen(QPen(QColor(50, 50, 50)))
        title = f"传感器 {self.channel_idx + 1} 肌电数据折线图"
        painter.drawText(title_rect, Qt.AlignCenter, title)

        # 在标题下添加分隔线
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawLine(0, 40, self.width(), 40)

        # 2. 绘制图例区域 (标题下方30像素))
        legend_rect = QRect(0, 40, self.width(), 30)
        painter.fillRect(legend_rect, QColor(250, 250, 250))

        # 绘制图例
        legend_title_font = QFont("SimHei", 12)
        painter.setFont(legend_title_font)
        painter.setPen(QPen(QColor(80, 80, 80)))

        # 绘制颜色方块
        legend_item = QRect(20, 45, 120, 20)
        painter.fillRect(legend_item.x(), legend_item.y(), 20, 15, self.channel_color)

        # 绘制传感器名称
        painter.drawText(legend_item.x() + 25, 45, 200, 20,
                         Qt.AlignLeft | Qt.AlignVCenter, self.channel_names[self.channel_idx])

        # 3. 绘制图例下方的分隔线
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(0, 70, self.width(), 70)

        # 4. 绘制主图表区域 (图例下方)
        chart_top = 70
        chart_height = available_height - chart_top

        # 绘制图表背景
        chart_rect = QRect(0, chart_top, self.width(), chart_height)
        painter.fillRect(chart_rect, Qt.white)

        # 计算绘图区域内的位置
        plot_margin = 40
        plot_x = plot_margin
        plot_y = chart_top + plot_margin
        plot_width = self.width() - 2 * plot_margin
        plot_height = chart_height - 2 * plot_margin - 20  # 额外减去20像素防止溢出

        # 绘制图表边框
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(plot_x, plot_y, plot_width, plot_height)

        # 绘制Y轴标签和刻度
        axis_font = QFont("Arial", 8)
        painter.setFont(axis_font)
        painter.setPen(QPen(QColor(80, 80, 80)))

        # Y轴标签（传感器值0-1024）
        for value in [0, 256, 512, 768, 1024]:
            y_pos = plot_y + plot_height - int((value / 1024) * plot_height)
            painter.drawText(10, y_pos - 6, 25, 12, Qt.AlignRight, str(value))
            # 绘制刻度线
            painter.drawLine(plot_x, y_pos, plot_x - 5, y_pos)

        # 绘制网格线（水平线和垂直线）
        grid_pen = QPen(QColor(220, 220, 220), 1)
        painter.setPen(grid_pen)

        # 水平网格线
        for i in range(1, 5):  # 4条水平线
            y_pos = plot_y + int(i * plot_height / 4)
            painter.drawLine(plot_x, y_pos, plot_x + plot_width, y_pos)

        # 垂直网格线（每20个数据点一条）
        if self.history_size > 0:
            for i in range(1, 5):  # 4条垂直线
                x_pos = plot_x + int(i * plot_width / 4)
                painter.drawLine(x_pos, plot_y, x_pos, plot_y + plot_height)

        # 绘制数据线（当前通道）
        pen = QPen(self.channel_color, 3)
        painter.setPen(pen)

        if np.any(self.data != 0):
            # 确保Y坐标在有效范围内
            def clamp_y(y):
                return max(plot_y, min(plot_y + plot_height, y))

            # 绘制每条传感器数据
            for i in range(1, len(self.data)):
                # 计算前一个点和当前点的位置
                prev_x = plot_x + int(((i - 1) / self.history_size) * plot_width)
                prev_val = max(0, min(1024, self.data[i - 1]))
                prev_y = clamp_y(plot_y + plot_height - int((prev_val / 1024) * plot_height))

                curr_x = plot_x + int((i / self.history_size) * plot_width)
                curr_val = max(0, min(1024, self.data[i]))
                curr_y = clamp_y(plot_y + plot_height - int((curr_val / 1024) * plot_height))

                # 绘制线段
                painter.drawLine(prev_x, prev_y, curr_x, curr_y)

        # 5. 绘制底部状态区域(30像素)
        status_rect = QRect(0, available_height, self.width(), 30)
        painter.fillRect(status_rect, QColor(245, 245, 245))

        # 添加底部边框
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(0, available_height, self.width(), available_height)

        # 添加当前值标签
        if len(self.data) > 0:
            last_value = int(self.data[-1])
            painter.setPen(QPen(QColor(50, 50, 50)))
            painter.drawText(status_rect, Qt.AlignLeft | Qt.AlignVCenter,
                             f"当前值: {last_value}")


class MultiChannelPlotWidget(QWidget):
    """多通道传感器数据绘图部件"""
    def __init__(self, sensor_count=8, history_size=100, parent=None):
        """
        初始化多通道绘图部件

        参数:
            sensor_count: 传感器数量(默认8)
            history_size: 历史数据点数量
            parent: 父部件
        """
        super().__init__(parent)
        self.sensor_count = sensor_count    # 传感器数量
        self.history_size = history_size    # 历史数据长度
        self.data = np.zeros((sensor_count, history_size))  # 初始化数据数组

        # 设置尺寸策略允许伸缩
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 改进的颜色方案，更易区分
        self.colors = [
            QColor(230, 25, 75),  # Red
            QColor(60, 180, 75),  # Green
            QColor(0, 130, 200),  # Blue
            QColor(245, 130, 48),  # Orange
            QColor(145, 30, 180),  # Purple
            QColor(70, 240, 240),  # Cyan
            QColor(240, 50, 230),  # Magenta
            QColor(210, 245, 60)  # Lime
        ]

        self.sensor_names = [
            "传感器1",
            "传感器2",
            "传感器3",
            "传感器4",
            "传感器5",
            "传感器6",
            "传感器7",
            "传感器8"
        ]

    def add_data(self, new_data):
        """
        添加新数据点

        参数:
            new_data: 包含8个传感器值的列表/数组
        """
        if len(new_data) >= self.sensor_count:
            # 向左移动旧数据
            self.data[:, :-1] = self.data[:, 1:]
            # 添加新数据到末尾
            for i in range(self.sensor_count):
                self.data[i, -1] = new_data[i]

    def paintEvent(self, event):
        """
        绘制部件内容

        参数:
            event: 绘制事件
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)# 启用抗锯齿

        # 0. 获取实际可用高度
        total_height = self.height()
        available_height = total_height - 30  # 为底部状态栏预留30像素

        # 1. 绘制标题区域 (顶部)
        title_font = QFont("SimHei", 20, QFont.Bold)
        painter.setFont(title_font)

        # 绘制标题背景
        title_rect = QRect(0, 0, self.width(), 40)
        painter.fillRect(title_rect, QColor(240, 240, 240))

        # 绘制标题
        painter.setPen(QPen(QColor(50, 50, 50)))
        painter.drawText(title_rect, Qt.AlignCenter, "8通道肌电传感器数据折线图（合）")

        # 在标题下添加分隔线
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawLine(0, 40, self.width(), 40)

        # 2. 绘制图例区域 (标题下方)
        legend_rect = QRect(0, 40, self.width(), 30)
        painter.fillRect(legend_rect, QColor(250, 250, 250))

        # 绘制图例标题
        legend_title_font = QFont("SimHei", 12)
        painter.setFont(legend_title_font)
        painter.setPen(QPen(QColor(80, 80, 80)))
        painter.drawText(10, 40, 80, 30, Qt.AlignVCenter, "传感器图例:")

        # 计算每个图例项的宽度
        item_width = (self.width() - 100) // self.sensor_count

        # 绘制每个传感器的图例
        for i in range(self.sensor_count):
            x_start = 100 + i * item_width
            legend_item = QRect(int(x_start), 45, int(item_width - 10), 20)

            # 绘制颜色方块
            painter.fillRect(legend_item.x(), legend_item.y(), 20, 15, self.colors[i])

            # 绘制传感器名称
            painter.setPen(QPen(QColor(50, 50, 50)))
            painter.drawText(legend_item.x() + 25, 45, item_width - 40, 20,
                             Qt.AlignLeft | Qt.AlignVCenter, self.sensor_names[i])

        # 3. 绘制图例下方的分隔线
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(0, 70, self.width(), 70)

        # 4. 绘制主图表区域 (图例下方)
        chart_top = 70
        chart_height = available_height - chart_top

        # 绘制图表背景
        chart_rect = QRect(0, chart_top, self.width(), chart_height)
        painter.fillRect(chart_rect, Qt.white)

        # 计算绘图区域内的位置
        plot_margin = 40
        plot_x = plot_margin
        plot_y = chart_top + plot_margin
        plot_width = self.width() - 2 * plot_margin
        plot_height = chart_height - 2 * plot_margin - 20  # 额外减去20像素防止溢出

        # 绘制图表边框
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(plot_x, plot_y, plot_width, plot_height)

        # 绘制Y轴标签
        axis_font = QFont("Arial", 8)
        painter.setFont(axis_font)
        painter.setPen(QPen(QColor(80, 80, 80)))

        # Y轴标签（传感器值0-1024）
        for value in [0, 256, 512, 768, 1024]:
            y_pos = plot_y + plot_height - int((value / 1024) * plot_height)
            painter.drawText(10, y_pos - 6, 25, 12, Qt.AlignRight, str(value))
            # 绘制刻度线
            painter.drawLine(plot_x, y_pos, plot_x - 5, y_pos)

        # 绘制网格线（水平线）
        grid_pen = QPen(QColor(220, 220, 220), 1)
        painter.setPen(grid_pen)
        for i in range(1, 5):  # 4条水平线
            y_pos = plot_y + int(i * plot_height / 4)
            painter.drawLine(plot_x, y_pos, plot_x + plot_width, y_pos)

        # 绘制数据线（8条传感器数据）
        if plot_width > 0 and plot_height > 0:
            # 确保Y坐标在有效范围内
            def clamp_y(y):
                return max(plot_y, min(plot_y + plot_height, y))

            for sensor in range(self.sensor_count):
                # 如果这个传感器有数据
                if np.any(self.data[sensor] != 0):
                    # 设置传感器颜色
                    pen = QPen(self.colors[sensor], 2)
                    painter.setPen(pen)

                    # 绘制每条传感器数据
                    for i in range(1, self.history_size):
                        # 计算前一个点和当前点的位置
                        prev_x = plot_x + int(((i - 1) / self.history_size) * plot_width)
                        prev_val = max(0, min(1024, self.data[sensor, i - 1]))
                        prev_y = clamp_y(plot_y + plot_height - int((prev_val / 1024) * plot_height))

                        curr_x = plot_x + int((i / self.history_size) * plot_width)
                        curr_val = max(0, min(1024, self.data[sensor, i]))
                        curr_y = clamp_y(plot_y + plot_height - int((curr_val / 1024) * plot_height))

                        # 绘制线段
                        painter.drawLine(prev_x, prev_y, curr_x, curr_y)

        # 5. 绘制底部状态区域
        status_rect = QRect(0, available_height, self.width(), 30)
        painter.fillRect(status_rect, QColor(245, 245, 245))

        # 添加底部边框
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(0, available_height, self.width(), available_height)


class PlottingWindow(QMainWindow):
    """主绘图窗口"""
    def __init__(self, parent=None):
        """
        初始化主窗口

        参数:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("肌电传感器监控系统 - ATK-DL2k0300龙芯开发板")
        self.setFixedSize(1024, 600)     # 固定窗口大小


        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 创建工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #f5f5f5; border-radius: 4px;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(15)

        # 添加标题标签
        title_label = QLabel("肌电传感器数据监控")
        title_label.setFont(QFont("SimHei", 14, QFont.Bold))
        toolbar_layout.addWidget(title_label)

        # 添加弹性空间使按钮居右
        toolbar_layout.addStretch()
        # 添加返回多通道视图按钮(初始隐藏)
        self.back_to_multi_button = QPushButton("返回多通道视图")
        self.back_to_multi_button.setFont(QFont("SimHei", 10))
        self.back_to_multi_button.setFixedWidth(150)
        self.back_to_multi_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f0f0f0;
                        border: 1px solid #d0d0d0;
                        border-radius: 4px;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                """)
        toolbar_layout.addWidget(self.back_to_multi_button)
        self.back_to_multi_button.hide()  # 初始隐藏
        # 添加返回按钮
        self.back_button = QPushButton("返回主控制界面")
        self.back_button.setFont(QFont("SimHei", 10))
        self.back_button.setFixedWidth(150)
        self.back_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        toolbar_layout.addWidget(self.back_button)

        # 添加通道选择按钮
        self.channels_button = QPushButton("分别查看各通道数据折线图")
        self.channels_button.setFont(QFont("SimHei", 10))
        self.channels_button.setFixedWidth(220)
        self.channels_button.setStyleSheet("""
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: 1px solid #3a76d8;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
        """)
        toolbar_layout.addWidget(self.channels_button)

        main_layout.addWidget(toolbar)

        # 创建视图切换框架
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("""
            QStackedWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.stacked_widget, 1)

        # 创建多通道视图
        self.multi_channel_view = MultiChannelPlotWidget()
        self.stacked_widget.addWidget(self.multi_channel_view)

        # 创建单通道选项卡视图
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #cccccc;
            }
            QTabBar::tab {
                background: #f0f0f0;
                color: #333;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                font: 10pt 'SimHei';
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #0066cc;
                font-weight: bold;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background: #e0e0e0;
            }
        """)

        # 创建8个单通道视图
        self.single_channel_views = []
        for i in range(8):
            channel_widget = SingleChannelPlotWidget(i)
            self.tab_widget.addTab(channel_widget, f"传感器 {i + 1}")
            self.single_channel_views.append(channel_widget)

        self.stacked_widget.addWidget(self.tab_widget)

        # 默认显示多通道视图
        self.current_view = "multi"
        self.stacked_widget.setCurrentIndex(0)

        # 添加底部状态标签
        self.status_bar = QLabel("正在等待传感器数据...")
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                color: #404040;
                font-family: SimHei;
                padding: 5px 10px;
            }
        """)
        main_layout.addWidget(self.status_bar)

        # 设置定时器控制刷新率
        self.timer = QTimer(self)
        self.timer.setInterval(1000)  # 1000ms刷新一次
        self.timer.timeout.connect(self.update_sensor_data_plots)
        self.timer.start()

        # 连接按钮信号
        self.channels_button.clicked.connect(self.switch_to_single_channel_view)
        self.back_button.clicked.connect(self.switch_to_main_control)
        self.back_to_multi_button.clicked.connect(self.switch_to_multi_channel_view)  # 新增
    def switch_to_single_channel_view(self):
        """切换到单通道视图"""
        self.current_view = "single"
        self.stacked_widget.setCurrentIndex(1)
        self.channels_button.hide()
        self.back_button.show()
        self.back_to_multi_button.show()  # 显示返回多通道视图按钮
        self.status_bar.setText("已切换到单通道视图 - 选择上方标签页查看不同传感器数据")

    def switch_to_multi_channel_view(self):
        """切换回多通道视图"""
        self.current_view = "multi"
        self.stacked_widget.setCurrentIndex(0)
        self.channels_button.show()
        self.back_button.hide()
        self.back_to_multi_button.hide()  # 隐藏返回多通道视图按钮
        self.status_bar.setText("已切换回多通道视图")

    def switch_to_main_control(self):
        """返回到主控制界面"""
        self.status_bar.setText("正在返回主控制界面...")
        self.parent().show_main_control()
        self.hide()

    def update_sensor_data_plots(self):
        """更新图表数据"""
        try:
            if not os.path.exists(SENSOR_DATA_FILE):
                self.reset_all_sensors()
                return

            with open(SENSOR_DATA_FILE, 'r') as f:
                content = f.read().strip()

            if content:
                sensor_vals = content.split()
                if len(sensor_vals) >= 8:
                    data = []
                    for i in range(8):
                        try:
                            raw_val = int(sensor_vals[i])
                            data.append(raw_val)
                        except:
                            data.append(0)

                    # 更新多通道视图
                    self.multi_channel_view.add_data(data)

                    # 更新所有单通道视图
                    for view in self.single_channel_views:
                        view.add_data(data)

                    # 重绘当前视图
                    if self.current_view == "multi":
                        self.multi_channel_view.update()
                    else:
                        current_tab = self.tab_widget.currentIndex()
                        if 0 <= current_tab < len(self.single_channel_views):
                            self.single_channel_views[current_tab].update()

                    return
        except Exception as e:
            self.status_bar.setText(f"读取传感器数据文件错误: {e}")

        self.reset_all_sensors()

    def reset_all_sensors(self):
        """重置所有传感器数据显示为0"""
        for view in self.single_channel_views:
            view.add_data([0] * 8)
        self.multi_channel_view.add_data([0] * 8)
