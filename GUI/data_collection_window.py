#data_collcetion_window.py
from PyQt5 import Qt
from PyQt5.QtCore import QTimer,Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QGridLayout

from core.collection import EMGHandler, MyoWorker, DataManager


class DataCollectionWindow(QMainWindow):
    """
        肌电数据采集主窗口类
        继承自QMainWindow，提供数据采集系统的主界面
        """
    def __init__(self, parent=None):
        """
                初始化数据采集窗口

                参数：
                    parent: 父窗口对象
                """
        super().__init__(parent)
        self.setWindowTitle("肌电手势数据收集系统 - ATK-DL2k0300龙芯开发板")
        self.setFixedSize(1024, 600)    # 固定窗口大小

        # 初始化数据管理组件
        self.data_manager = DataManager()   # 数据存储管理
        self.data_collection_app = DataCollectionApp(self.data_manager)

        # 创建中央部件和主布局
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

        # 添加标题
        title_label = QLabel("肌电手势数据收集")
        title_label.setFont(QFont("SimHei", 14, QFont.Bold))
        toolbar_layout.addWidget(title_label)

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

        main_layout.addWidget(toolbar)

        # 创建主内容区域
        self.content_widget = QWidget()
        main_layout.addWidget(self.content_widget, 1) # 1表示可伸缩区域
        self.status_bar = QLabel("准备开始数据收集...")
        # 初始化UI
        self.init_data_collection_ui()

        # 连接信号
        self.back_button.clicked.connect(self.switch_to_main_control)

        # 创建状态栏

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

    def init_data_collection_ui(self):
        """初始化数据收集界面"""
        # 清除现有内容
        if hasattr(self, 'content_layout'):
            QWidget().setLayout(self.content_layout)
        # 创建内容区域布局
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        # 初始化数据采集应用的UI组件
        self.data_collection_app.window = self  # 传递窗口引用
        self.data_collection_app.init_ui_components(self.content_layout)

        # 将状态栏引用传递给数据采集应用
        self.data_collection_app.connection_label = self.status_bar
    def switch_to_main_control(self):
        """返回主控制界面（与PlottingWindow相同的逻辑）"""
        self.status_bar.setText("正在返回主控制界面...")
        self.parent().show_main_control()
        self.hide()

class DataCollectionApp:
    """
        数据采集应用逻辑类
        处理Myo设备连接、数据采集和界面交互逻辑
        """
    def __init__(self, data_manager):
        """
               初始化数据采集应用

               参数：
                   data_manager: 数据管理对象
               """
        self.data_manager = data_manager
        self.emg_handler = EMGHandler(self)  # EMG信号处理器
        self.last_pose = None               # 记录最后识别到的手势
        self.is_connected = False           # Myo连接状态标志
        self.myo_worker = MyoWorker()       # 连接EMG信号处理槽函数
        self.myo_worker.emg_signal.connect(self.handle_emg_signal)# 连接EMG信号处理槽函数

        # 手势名称映射
        self.gesture_mapping = {
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

        # UI组件引用
        self.buttons = []  # 手势按钮列表
        self.count_labels = []  # 数据计数标签列表
        self.connection_label = None  # 连接状态标签
        self.channel_label = None  # 当前采集手势显示
        self.connect_button = None  # 连接按钮
        self.pause_button = None  # 暂停按钮


        # 定时器
        self.update_timer = QTimer()    # 用于更新界面计数
        self.update_timer.timeout.connect(self.update_counts)
        self.flush_timer = QTimer()     # 用于定期保存数据
        self.flush_timer.timeout.connect(self.flush_buffers)

    def init_ui_components(self, parent_layout):
        """初始化UI组件"""
        # 标题
        title_label = QLabel("肌电手势数据收集系统")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1A237E; margin-bottom: 10px;")
        parent_layout.addWidget(title_label)

        # 手势按钮区域
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        grid_layout.setContentsMargins(10, 10, 10, 10)
        parent_layout.addLayout(grid_layout)

        # 手势按钮（0-9）
        button_colors = [
            "#FFCDD2", "#F8BBD0", "#E1BEE7", "#D1C4E9",
            "#C5CAE9", "#BBDEFB", "#B3E5FC", "#B2EBF2",
            "#B2DFDB", "#C8E6C9"
        ]
        # 创建10个手势按钮和对应的计数标签
        for i in range(10):
            row = i // 5
            col = i % 5

            # 创建手势按钮
            button = QPushButton(self.gesture_mapping[i])
            button.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            button.setFixedSize(140, 50)
            # 设置按钮样式
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {button_colors[i]};
                    color: #212121;
                    border-radius: 8px;
                    border: 1px solid #BDBDBD;
                }}
                QPushButton:hover {{
                    background-color: #E0E0E0;
                    border: 1px solid #9E9E9E;
                }}
            """)
            # 连接按钮点击信号
            button.clicked.connect(lambda checked, idx=i: self.set_recording(idx))
            grid_layout.addWidget(button, row * 2, col)
            self.buttons.append(button)

            # 创建计数标签
            count_label = QLabel("0")
            count_label.setFont(QFont("Arial", 14, QFont.Bold))
            count_label.setAlignment(Qt.AlignCenter)
            count_label.setStyleSheet("color: #D32F2F;")
            grid_layout.addWidget(count_label, row * 2 + 1, col)
            self.count_labels.append(count_label)

        # 控制按钮区域
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)
        parent_layout.addLayout(control_layout)

        # 连接按钮
        self.connect_button = QPushButton('连接Myo')
        self.connect_button.setFont(QFont("Microsoft YaHei", 12))
        self.connect_button.setFixedHeight(45)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
                color: #757575;
            }
        """)
        self.connect_button.clicked.connect(self.connect_to_myo)
        control_layout.addWidget(self.connect_button)

        # 创建暂停按钮
        self.pause_button = QPushButton('暂停记录')
        self.pause_button.setFont(QFont("Microsoft YaHei", 12))
        self.pause_button.setFixedHeight(45)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.pause_button.clicked.connect(self.pause_recording)
        control_layout.addWidget(self.pause_button)

        # 清除按钮按钮
        clear_button = QPushButton('清除数据')
        clear_button.setFont(QFont("Microsoft YaHei", 12))
        clear_button.setFixedHeight(45)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        clear_button.clicked.connect(self.clear_data)
        control_layout.addWidget(clear_button)

        # 当前状态显示标签
        self.channel_label = QLabel("当前正在记录手势为: 无")
        self.channel_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.channel_label.setAlignment(Qt.AlignCenter)
        self.channel_label.setStyleSheet("""
            background-color: #B3E5FC;
            color: #01579B;
            padding: 12px;
            border-radius: 8px;
            margin-top: 10px;
            margin-bottom: 10px;
        """)
        parent_layout.addWidget(self.channel_label)

        # 底部提示
        bottom_info = QLabel("提示：确保Myo肌电臂环已充电并蓝牙已配对\n正确佩戴在手臂上，做手势时保持前臂放松、动作清晰")
        bottom_info.setFont(QFont("Microsoft YaHei", 10))
        bottom_info.setAlignment(Qt.AlignCenter)
        bottom_info.setStyleSheet("color: #616161;")
        parent_layout.addWidget(bottom_info)

        # 启动定时器
        self.update_timer.start(500)    # 每500ms更新一次计数
        self.flush_timer.start(1000)    # 每1000ms保存一次数据

    def handle_emg_signal(self, emg, moving):
        """
                处理来自Myo设备的EMG信号

                参数：
                    emg: 肌电信号数据
                    moving: 是否检测到移动
                """
        self.emg_handler(emg, moving)

    def connect_to_myo(self):
        """连接或断开Myo设备"""
        if not self.is_connected:
            # 尝试连接Myo
            success, message = self.myo_worker.connect_myo()
            if success:
                self.is_connected = True
                # 更新连接按钮状态
                self.connect_button.setText("断开连接")
                self.connect_button.setStyleSheet("""
                    QPushButton {
                        background-color: #F44336;
                        color: white;
                        border-radius: 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #D32F2F;
                    }
                """)
                self.myo_worker.start() # 启动工作线程
                # 更新连接状态显示
                if self.connection_label:
                    self.connection_label.setText("设备状态: 已连接")
                    self.connection_label.setStyleSheet("padding: 8px; background-color: #C8E6C9; border-radius: 5px;")
            else:
                # 显示连接错误
                if self.connection_label:
                    self.connection_label.setText(f"设备状态: {message}")
                    self.connection_label.setStyleSheet("padding: 8px; background-color: #FFCDD2; border-radius: 5px;")
        else:
            self.disconnect_myo()

    def disconnect_myo(self):
        """断开Myo设备连接"""
        if self.myo_worker.isRunning():
            self.myo_worker.stop()  # 停止工作线程
            self.myo_worker.wait()  # 等待线程结束

        self.is_connected = False
        # 恢复连接按钮状态
        self.connect_button.setText("连接Myo")
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        # 更新连接状态显示
        if self.connection_label:
            self.connection_label.setText("设备状态: 未连接")
            self.connection_label.setStyleSheet("padding: 8px; background-color: #FFCDD2; border-radius: 5px;")

    def set_recording(self, cls):
        """
                设置当前要记录的手势类型

                参数：
                    cls: 手势ID (0-9)
                """
        self.emg_handler.recording = cls
        self.emg_handler.recording_enabled = True
        # 更新当前采集状态显示
        self.channel_label.setText(f"当前正在记录手势为: {self.gesture_mapping[cls]}")

        # 更新所有按钮状态
        for i, button in enumerate(self.buttons):
            if i == cls:
                # 设置当前选中按钮样式
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #FF5722;
                        color: white;
                        border: 2px solid #BF360C;
                        border-radius: 8px;
                        font-weight: bold;
                    }}
                """)
            else:
                # 设置非选中按钮样式
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #E0E0E0;
                        color: #212121;
                        border: 1px solid #BDBDBD;
                        border-radius: 8px;
                    }}
                    QPushButton:hover {{
                        background-color: #BDBDBD;
                        border: 1px solid #9E9E9E;
                    }}
                """)

    def pause_recording(self):
        """切换暂停/继续记录状态"""
        self.emg_handler.recording_enabled = not self.emg_handler.recording_enabled
        if self.emg_handler.recording_enabled:
            # 恢复记录状态
            self.pause_button.setText("暂停记录")
            self.pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)
            self.channel_label.setText(f"当前正在记录手势为: {self.gesture_mapping[self.emg_handler.recording]}")
        else:
            # 暂停状态
            self.pause_button.setText("继续记录")
            self.pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #388E3C;
                }
            """)
            self.channel_label.setText("当前正在记录手势为: 已暂停")

    def clear_data(self):
        """清除所有已采集的数据"""
        self.data_manager.delete_data()
        self.update_counts()    # 更新界面显示
    def update_count(self, cls):
        """
                更新单个手势的计数显示

                参数：
                    cls: 要更新的手势ID
                """
        """更新单个手势的计数显示"""
        try:
            count = self.data_manager.get_count(cls)
            self.count_labels[cls].setText(str(count))
        except Exception as e:
            print(f"更新计数错误: {e}")
    def update_counts(self):
        """更新所有手势的计数显示"""
        for i in range(10):
            try:
                count = self.data_manager.get_count(i)
                self.count_labels[i].setText(str(count))
            except Exception as e:
                print(f"更新计数错误: {e}")
                self.count_labels[i].setText("0")

    def flush_buffers(self):
        """定期刷新所有缓冲区到文件"""
        self.data_manager.flush_all_buffers()

    def cleanup(self):
        """清理资源，在程序退出时调用"""
        self.update_timer.stop()    # 停止UI更新定时器
        self.flush_timer.stop()     # 停止数据保存定时器
        self.disconnect_myo()        # 断开设备连接
        self.data_manager.flush_all_buffers()    # 确保所有数据已保存