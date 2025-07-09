#main_window.py
import os

from PyQt5 import QtWidgets, QtCore, QtGui

from .data_collection_window import DataCollectionWindow
from .plotting_windows import PlottingWindow
from core.classifier import GestureRecognitionThread
from config import GESTURE_FILE, SENSOR_DATA_FILE


class EMGControlGUI(QtWidgets.QMainWindow):
    """
    肌电控制仿生手系统主界面类，继承自QMainWindow
    负责创建和管理整个应用程序的主界面
    """
    def __init__(self):
        super().__init__()
        self.init_ui() # 初始化用户界面
        # 创建手势识别线程
        self.recognition_thread = GestureRecognitionThread()
        # 连接信号与槽
        self.recognition_thread.status_signal.connect(self.update_status)
        self.recognition_thread.sensor_active_signal.connect(self.set_sensor_active)
        self.recognition_thread.connection_success.connect(self.on_connection_success)

        # 创建绘图窗口（但先不显示）
        self.plotting_window = PlottingWindow(self)
        self.plotting_window.hide()
        # 创建数据收集窗口（但先不显示）
        self.data_collection_window = DataCollectionWindow(self)
        self.data_collection_window.hide()

        # 保存状态信息的变量
        self.last_status = "系统状态: 初始化完成，等待连接指令"
        self.setup_timers()     # 设置定时器
        self.connect_signals()  # 连接信号与槽
        self.update_gesture_display()# 更新手势显示

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("龙芯肌电控制仿生手系统")
        self.setFixedSize(1024, 600)  # 固定窗口尺寸
        self.setStyleSheet("QMainWindow { background-color: #f0f5ff; }")

        # 中央部件
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 5)  # 减少底部边距
        self.main_layout.setSpacing(8)

        # 页眉
        header_layout = QtWidgets.QHBoxLayout()

        # 左logo
        left_logo_container = QtWidgets.QFrame()
        left_logo_container.setFixedSize(80, 60)
        self.left_logo_label = QtWidgets.QLabel()
        self.left_logo_label.setFixedSize(60, 45)
        self.load_logo(self.left_logo_label, "GUI/picture/loongson_logo.png", "龙芯")
        left_logo_layout = QtWidgets.QVBoxLayout(left_logo_container)
        left_logo_layout.addWidget(self.left_logo_label, 0, QtCore.Qt.AlignCenter)
        header_layout.addWidget(left_logo_container)

        # 标题区域
        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QVBoxLayout(title_container)
        title_label = QtWidgets.QLabel("龙芯肌电控制仿生手系统")
        title_label.setFont(QtGui.QFont("黑体", 18, QtGui.QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_layout.addWidget(title_label)
        project_label = QtWidgets.QLabel("龙芯开发板ATK-DL2K0300 | 信息显示系统")
        project_label.setFont(QtGui.QFont("微软雅黑", 10))
        project_label.setStyleSheet("color: #7f8c8d;")
        project_label.setAlignment(QtCore.Qt.AlignCenter)
        title_layout.addWidget(project_label)
        header_layout.addWidget(title_container, 1)

        # 右logo
        right_logo_container = QtWidgets.QFrame()
        right_logo_container.setFixedSize(80, 60)
        self.right_logo_label = QtWidgets.QLabel()
        self.right_logo_label.setFixedSize(60, 45)
        self.load_logo(self.right_logo_label, "GUI/picture/embedded_logo.png", "嵌入式")
        right_logo_layout = QtWidgets.QVBoxLayout(right_logo_container)
        right_logo_layout.addWidget(self.right_logo_label, 0, QtCore.Qt.AlignCenter)
        header_layout.addWidget(right_logo_container)

        self.main_layout.addLayout(header_layout)

        # 主要内容区域
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(content_widget, 1)

        # 手势识别区域 - 修复标题被遮挡问题
        gesture_frame = self.create_groupbox("手势识别")
        gesture_layout = QtWidgets.QVBoxLayout(gesture_frame)
        gesture_layout.setContentsMargins(10, 25, 10, 10)

        # 手势图标显示
        gesture_icon_frame = QtWidgets.QFrame()
        gesture_icon_frame.setStyleSheet("background-color: white; border-radius: 6px;")
        gesture_icon_frame.setMinimumHeight(220)
        icon_layout = QtWidgets.QVBoxLayout(gesture_icon_frame)
        icon_layout.setSpacing(5)

        self.gesture_icon = QtWidgets.QLabel()
        self.gesture_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.gesture_icon.setFont(QtGui.QFont("微软雅黑", 24, QtGui.QFont.Bold))
        icon_layout.addWidget(self.gesture_icon)

        self.gesture_label = QtWidgets.QLabel("无手势")
        self.gesture_label.setFont(QtGui.QFont("微软雅黑", 20, QtGui.QFont.Bold))
        self.gesture_label.setAlignment(QtCore.Qt.AlignCenter)
        self.gesture_label.setStyleSheet("color: #7f8c8d; padding: 5px 0;")
        icon_layout.addWidget(self.gesture_label)

        gesture_desc = QtWidgets.QLabel("当前识别手势")
        gesture_desc.setFont(QtGui.QFont("微软雅黑", 12))
        gesture_desc.setAlignment(QtCore.Qt.AlignCenter)
        gesture_desc.setStyleSheet("color: #7f8c8d;")
        icon_layout.addWidget(gesture_desc)

        gesture_layout.addWidget(gesture_icon_frame)

        # 状态信息
        info_label = QtWidgets.QLabel("点击'连接手环'按钮后开始识别")
        info_label.setFont(QtGui.QFont("微软雅黑", 10))
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_label.setStyleSheet("color: #7f8c8d; padding: 5px 0;")
        gesture_layout.addWidget(info_label)

        # 状态指示灯
        status_indicator = QtWidgets.QFrame()
        status_layout = QtWidgets.QHBoxLayout(status_indicator)
        connection_label = QtWidgets.QLabel("手环连接状态:")
        connection_label.setFont(QtGui.QFont("微软雅黑", 11))
        status_layout.addWidget(connection_label)

        self.connection_indicator = QtWidgets.QLabel()
        self.connection_indicator.setFixedSize(18, 18)
        self.connection_indicator.setStyleSheet("background-color: #bdc3c7; border-radius: 9px;")
        status_layout.addWidget(self.connection_indicator)
        status_layout.addStretch(1)
        gesture_layout.addWidget(status_indicator)

        content_layout.addWidget(gesture_frame, 2)

        # 传感器数据显示区域
        sensor_frame = self.create_groupbox("肌电传感器数据")
        sensor_layout = QtWidgets.QVBoxLayout(sensor_frame)
        sensor_layout.setContentsMargins(10, 25, 10, 10)

        # 8个传感器的网格布局
        sensor_grid = QtWidgets.QGridLayout()
        sensor_grid.setHorizontalSpacing(15)
        sensor_grid.setVerticalSpacing(8)
        sensor_grid.setContentsMargins(10, 5, 10, 5)

        self.sensor_values = []
        self.sensor_bars = []

        for i in range(8):
            # 传感器标签
            label = QtWidgets.QLabel(f"传感器{i + 1}:")
            label.setFont(QtGui.QFont("微软雅黑", 11))
            label.setStyleSheet("color: #2c3e50;")
            sensor_grid.addWidget(label, i, 0)

            # 传感器进度条
            bar_frame = QtWidgets.QFrame()
            bar_frame.setFrameShape(QtWidgets.QFrame.Box)
            bar_frame.setMinimumSize(180, 25)
            bar_frame.setMaximumHeight(25)
            bar_frame.setStyleSheet("background-color: #e0e0e0; border-radius: 4px;")

            bar_inner = QtWidgets.QFrame(bar_frame)
            bar_inner.setGeometry(0, 0, 0, bar_frame.height())
            bar_inner.setStyleSheet("background-color: #3498db; border-radius: 4px;")

            sensor_grid.addWidget(bar_frame, i, 1)
            self.sensor_bars.append(bar_inner)

            # 传感器数值显示
            value_frame = QtWidgets.QFrame()
            value_frame.setFrameShape(QtWidgets.QFrame.Box)
            value_frame.setMinimumSize(50, 25)  # 减小高度
            value_frame.setMaximumHeight(25)  # 减小高度
            value_frame.setStyleSheet("background-color: white; border-radius: 4px;")
            value_layout = QtWidgets.QHBoxLayout(value_frame)

            sensor_value = QtWidgets.QLabel("0%")
            sensor_value.setFont(QtGui.QFont("微软雅黑", 10))  # 减小字体
            sensor_value.setAlignment(QtCore.Qt.AlignCenter)
            value_layout.addWidget(sensor_value)

            sensor_grid.addWidget(value_frame, i, 2)
            self.sensor_values.append(sensor_value)

            # 列宽比例设置
            sensor_grid.setColumnStretch(0, 1)
            sensor_grid.setColumnStretch(1, 4)
            sensor_grid.setColumnStretch(2, 1)

        sensor_layout.addLayout(sensor_grid)
        content_layout.addWidget(sensor_frame, 3)

        # 控制按钮区域
        control_area = QtWidgets.QWidget()
        control_layout = QtWidgets.QHBoxLayout(control_area)
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        control_layout.addStretch(1)

        # 数据收集按钮
        self.data_collection_btn = QtWidgets.QPushButton("数据收集")
        self.data_collection_btn.setFont(QtGui.QFont("微软雅黑", 16))  # 减小字体
        self.data_collection_btn.setMinimumSize(200, 40)  # 加宽按钮
        self.data_collection_btn.setMaximumSize(220, 45)
        self.data_collection_btn.setStyleSheet(self.get_button_style("#9b59b6", "#8e44ad"))

        # 连接手环按钮
        self.connect_btn = QtWidgets.QPushButton("连接手环")
        self.connect_btn.setFont(QtGui.QFont("微软雅黑", 16))  # 减小字体
        self.connect_btn.setMinimumSize(200, 40)  # 加宽按钮
        self.connect_btn.setMaximumSize(220, 45)
        self.connect_btn.setStyleSheet(self.get_button_style("#3498db", "#2980b9"))

        # 复位系统按钮
        self.reset_btn = QtWidgets.QPushButton("复位系统")
        self.reset_btn.setFont(QtGui.QFont("微软雅黑", 16))  # 减小字体
        self.reset_btn.setMinimumSize(200, 40)  # 加宽按钮
        self.reset_btn.setMaximumSize(220, 45)
        self.reset_btn.setStyleSheet(self.get_button_style("#e74c3c", "#c0392b"))

        # "查看数据折线图"按钮
        self.plot_view_btn = QtWidgets.QPushButton("查看数据折线图")
        self.plot_view_btn.setFont(QtGui.QFont("微软雅黑", 16))
        self.plot_view_btn.setMinimumSize(200, 40)
        self.plot_view_btn.setMaximumSize(220, 45)
        self.plot_view_btn.setStyleSheet(self.get_button_style("#f39c12", "#d35400"))

        control_layout.addWidget(self.data_collection_btn)
        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.reset_btn)
        control_layout.addWidget(self.plot_view_btn)
        control_layout.addStretch(1)
        self.main_layout.addWidget(control_area)

        # 状态栏
        status_widget = QtWidgets.QWidget()
        status_widget.setFixedHeight(25)
        status_layout = QtWidgets.QHBoxLayout(status_widget)
        status_layout.setContentsMargins(10, 2, 10, 2)

        self.status_label = QtWidgets.QLabel("系统状态: 初始化完成，等待连接指令")
        self.status_label.setFont(QtGui.QFont("微软雅黑", 9))
        self.status_label.setStyleSheet("color: #2c3e50;")
        status_layout.addWidget(self.status_label, 1)

        version_label = QtWidgets.QLabel("v3.0.0 © 2025")
        version_label.setFont(QtGui.QFont("微软雅黑", 8))
        version_label.setStyleSheet("color: #95a5a6;")
        status_layout.addWidget(version_label)

        status_widget.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #dcdcdc;")
        self.main_layout.addWidget(status_widget)

    def load_logo(self, label, filename, alt_text):
        """
        加载logo图片
        :param label: 要显示logo的QLabel
        :param filename: logo图片路径
        :param alt_text: 如果图片加载失败显示的替代文本
        :return: 是否成功加载图片
        """
        try:
            pixmap = QtGui.QPixmap(filename)
            if not pixmap.isNull():
                scaled = pixmap.scaled(label.size(),
                                       QtCore.Qt.KeepAspectRatio,
                                       QtCore.Qt.SmoothTransformation)
                label.setPixmap(scaled)
                return True
        except:
            pass

        label.setText(alt_text)
        label.setStyleSheet("font-weight: bold; font-size: 14px;")
        label.setAlignment(QtCore.Qt.AlignCenter)
        return False

    def create_groupbox(self, title):
        """
        创建带标题的分组框
        :param title: 分组框标题
        :return: 创建好的QGroupBox
        """
        frame = QtWidgets.QGroupBox(title)
        frame.setStyleSheet("""
            QGroupBox { 
                font-size: 16px;  /* 加大字体 */
                font-weight: bold;  /* 加粗 */
                color: #2c3e50;
                background-color: #f8f8f8; 
                border-radius: 8px;
                border: 1px solid #dcdcdc; 
                margin-top: 8px;
            }
            QGroupBox::title { 
                subcontrol-position: top center;
                padding: 5px 4px;
                top: -10px;  /* 调整标题位置 */
            }
        """)
        return frame

    def get_button_style(self, color, hover_color):
        """
        获取按钮的样式表
        :param color: 正常状态颜色
        :param hover_color: 悬停状态颜色
        :return: 样式表字符串
        """
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 6px; padding: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """

    def setup_timers(self):
        """设置定时器"""
        # 手势更新定时器
        self.gesture_timer = QtCore.QTimer()
        self.gesture_timer.timeout.connect(self.update_gesture_display)
        self.gesture_timer.start(300)   # 每300ms更新一次手势显示

        # 传感器数据更新定时器
        self.sensor_timer = QtCore.QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_data)
        self.sensor_timer.start(1000)   # 每1秒更新一次传感器数据

    def connect_signals(self):
        """连接信号与槽"""
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.reset_btn.clicked.connect(self.reset_system)
        self.data_collection_btn.clicked.connect(self.show_data_collection)
        self.plot_view_btn.clicked.connect(self.view_data_plots)
    def show_data_collection(self):
        """显示数据收集窗口"""
        self.last_status = self.status_label.text()
        self.update_status("跳转到数据收集界面...")
        self.hide()
        self.data_collection_window.show()
    def view_data_plots(self):
        """显示数据可视化窗口"""
        self.last_status = self.status_label.text()
        self.update_status("跳转到数据折线图分析界面...")
        self.hide()  # 隐藏主控制界面
        self.plotting_window.show()  # 显示数据可视化界面

    def show_main_control(self):
        """显示主控制界面"""
        self.plotting_window.hide()
        self.data_collection_window.hide()
        self.show()
        # 返回时恢复之前的状态信息
        self.update_status(self.last_status)  # 恢复保存的状态
    def update_status(self, message):
        """更新状态栏信息"""
        self.status_label.setText(message)

    def set_sensor_active(self, active):
        """设置传感器连接状态指示灯"""
        if active:
            self.connection_indicator.setStyleSheet("background-color: #2ecc71; border-radius: 9px;")
        else:
            self.connection_indicator.setStyleSheet("background-color: #bdc3c7; border-radius: 9px;")

    def on_connection_success(self, success):
        """处理连接成功信号"""
        if success:
            self.update_status("Myo设备已连接，开始手势识别")
            self.update_gesture_display()

    def get_gesture_name(self, gesture_id):
        """根据手势ID获取手势名称"""
        names = {
            -1: "无手势",
            0: "握拳",
            1: "伸食指",
            2: "哦耶",
            3: "OK",
            4: "数字四",
            5: "松弛",
            6: "点赞",
            7: "鹰爪",
            8: "摇滚",
            9: "夹吸管"
        }
        return names.get(gesture_id, "未知手势")

    def update_gesture_icon(self, gesture_id):
        """更新手势图标（英文名称）"""
        icons = {
            0: "Fist",
            1: "Number_1",
            2: "Victory",
            3: "Number_3",
            4: "Number_4",
            5: "none",
            6: "Thumbs-up",
            7: "Number_7",
            8: "Rock and Roll",
            9: "Hole something"
        }

        self.gesture_icon.setText(icons.get(gesture_id, ""))

    def update_gesture_display(self):
        """更新手势显示"""
        if not self.recognition_thread.connected:
            self.gesture_label.setText("请先连接手环")
            self.gesture_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
            self.gesture_icon.setText("")
            return

        try:
            if not os.path.exists(GESTURE_FILE):
                self.gesture_label.setText("文件缺失")
                return

            with open(GESTURE_FILE, 'r') as f:
                content = f.read().strip()

            if content:
                parts = content.split(',')
                if len(parts) >= 2:
                    gesture_id = int(parts[0])
                    confidence = float(parts[1])
                    gesture_name = self.get_gesture_name(gesture_id)

                    self.update_gesture_icon(gesture_id)

                    if confidence > 0.7:
                        self.gesture_label.setText(gesture_name)
                        if confidence > 0.85:
                            self.gesture_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                        elif confidence > 0.7:
                            self.gesture_label.setStyleSheet("color: #e67e22;")
                    else:
                        self.gesture_label.setText("识别中...")
                        self.gesture_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
                    return

        except Exception:
            pass

        self.gesture_label.setText("无手势识别结果")
        self.gesture_label.setStyleSheet("color: #7f8c8d;")
        self.gesture_icon.setText("")

    def update_sensor_data(self):
        """更新传感器数据显示"""
        try:
            if not os.path.exists(SENSOR_DATA_FILE):
                self.reset_all_sensors()
                return

            with open(SENSOR_DATA_FILE, 'r') as f:
                content = f.read().strip()

            if content:
                sensor_vals = content.split()
                if len(sensor_vals) >= 8:
                    for i in range(8):
                        try:
                            raw_val = int(sensor_vals[i])
                            percent = max(0, min(100, int((raw_val / 1024.0) * 100)))

                            self.sensor_values[i].setText(f"{percent}%")

                            bar_frame = self.sensor_bars[i].parent()
                            bar_width = int(bar_frame.width() * percent / 100.0)
                            self.sensor_bars[i].resize(bar_width, bar_frame.height())

                            bar_color = "#e74c3c" if percent > 80 else "#e67e22" if percent > 60 else "#3498db"
                            text_style = "color: #e74c3c; font-weight:bold; font-size:12px;" if percent > 80 else \
                                "color: #e67e22; font-weight:bold; font-size:12px;" if percent > 60 else \
                                    "color: #2c3e50; font-size:12px;"

                            self.sensor_bars[i].setStyleSheet(f"background-color: {bar_color}; border-radius:4px;")
                            self.sensor_values[i].setStyleSheet(text_style)
                        except:
                            continue
                    return

        except Exception:
            pass
        self.reset_all_sensors()

    def reset_all_sensors(self):
        """重置所有传感器显示"""
        for i in range(8):
            self.sensor_values[i].setText("0%")
            self.sensor_values[i].setStyleSheet("color: #2c3e50; font-weight:normal; font-size:12px;")
            bar_frame = self.sensor_bars[i].parent()
            self.sensor_bars[i].resize(0, bar_frame.height())
            self.sensor_bars[i].setStyleSheet("background-color: #3498db; border-radius:4px;")

    def toggle_connection(self):
        """切换手环连接状态"""
        if self.recognition_thread.connected or self.recognition_thread.should_connect:
            # 断开连接
            self.recognition_thread.stop_connection()
            self.connect_btn.setText("连接手环")
            self.connect_btn.setStyleSheet(self.get_button_style("#3498db", "#2980b9"))
            self.update_status("Myo设备已断开连接")
            self.gesture_label.setText("设备已断开")
            self.gesture_label.setStyleSheet("color: #7f8c8d;")
            self.gesture_icon.setText("")
        else:
            # 尝试连接
            self.recognition_thread.start_connection()
            self.connect_btn.setText("断开连接")
            self.connect_btn.setStyleSheet(self.get_button_style("#e74c3c", "#c0392b"))
            self.update_status("正在尝试连接Myo设备...")
            self.gesture_label.setText("连接中...")
            self.gesture_label.setStyleSheet("color: #f39c12; font-style: italic;")
            if not self.recognition_thread.isRunning():
                self.recognition_thread.start()

    def reset_system(self):
        """复位系统"""
        self.update_status("系统状态: 复位信号已发送...")

        # 断开Myo连接
        if self.recognition_thread.connected or self.recognition_thread.should_connect:
            self.recognition_thread.stop_connection()
            self.connect_btn.setText("连接手环")
            self.connect_btn.setStyleSheet(self.get_button_style("#3498db", "#2980b9"))

        # 初始化文件和传感器显示
        self.recognition_thread.init_files()
        self.reset_all_sensors()
        self.gesture_label.setText("无手势")
        self.gesture_icon.setText("")
        QtCore.QTimer.singleShot(1000, lambda: self.update_status("系统状态: 复位完成"))

    def collect_data(self):
        """收集数据"""
        self.update_status("系统状态: 数据收集中...")

    def closeEvent(self, event):
        """关闭窗口事件处理"""
        if self.recognition_thread.isRunning():
            self.recognition_thread.stop()
        super().closeEvent(event)
