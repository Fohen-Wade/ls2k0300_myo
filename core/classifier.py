#classifier.py
import os
import threading
import time
from collections import deque

import numpy as np
from PyQt5 import QtCore

from core.knn_cpp import KNNClassifier
from device.pyomyo import Myo, emg_mode
from device.UDP import GestureSender
from config import SENSOR_DATA_FILE, GESTURE_FILE


class GestureRecognitionThread(QtCore.QThread):
    """
        手势识别主线程类，继承自QThread用于Qt多线程

        信号:
            status_signal: 发送状态更新消息
            sensor_active_signal: 发送传感器活动状态
            connection_success: 连接成功信号
        """
    status_signal = QtCore.pyqtSignal(str)
    sensor_active_signal = QtCore.pyqtSignal(bool)
    connection_success = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        """
               初始化手势识别线程

               参数:
                   parent: 父对象(Qt对象)
               """
        super().__init__(parent)
        self.classifier = None      # KNN分类器实例
        self.myo_classifier = None  # Myo设备分类器
        self.running = False        # 线程运行标志
        self.connected = False      # 设备连接状态
        self.max_retries = 20       # 最大重试次数
        self.retry_delay = 1        # 重试延迟(秒)
        self.should_connect = False # 是否应该连接标志
        self.init_files()           # 初始化数据文件
        self.gesture_sender = GestureSender()# UDP手势发送器
        self.udp_active = False  # UDP活动状态标志

    def init_files(self):
        """初始化手势和传感器数据文件"""
        try:
            # 初始化手势文件(-1表示无手势)
            with open(GESTURE_FILE, 'w') as f:
                f.write("-1,0.0")
                # 初始化传感器数据文件(全零数据)
            with open(SENSOR_DATA_FILE, 'w') as f:
                f.write("0 0 0 0 0 0 0 0")
            self.status_signal.emit("系统状态: 手势文件初始化完成")
        except Exception as e:
            self.status_signal.emit(f"文件初始化失败: {e}")

    def run(self):
        """主线程运行函数"""
        self.running = True
        try:
            # 1. 初始化KNN分类器
            self.status_signal.emit("正在初始化KNN分类器...")
            self.classifier = KNNClassifier(k=5, max_samples=1500)
            self.status_signal.emit("C++ KNN分类器创建成功")

            # 2. 加载训练数据
            data_path = "data"
            if os.path.exists(data_path) and os.path.isdir(data_path):
                self.status_signal.emit(f"从目录加载训练数据: {data_path}")
                self.classifier.load_data(data_path)
                self.status_signal.emit("训练数据加载完成")
            else:
                self.status_signal.emit(f"警告: 训练数据目录 '{data_path}' 不存在")
            # 3. 创建Myo分类器实例
            self.myo_classifier = MyoClassifier(self.classifier)
        except Exception as e:
            self.status_signal.emit(f"分类器初始化失败: {e}")
            self.running = False
            return

        self.status_signal.emit("手势识别线程已启动，等待连接指令...")
        # 主循环
        while self.running:
            try:
                # 处理设备连接逻辑
                if not self.connected and self.should_connect:
                    self.status_signal.emit("正在尝试连接Myo设备...")
                    connection_result = self.connect_device()

                    if connection_result:
                        self.status_signal.emit("Myo设备已连接")
                        self.connected = True
                        self.sensor_active_signal.emit(True)

                        # 只在Myo连接成功后启动UDP发送线程
                        self.start_udp_sender()
                        self.connection_success.emit(True)  # 发射连接成功信号
                    else:
                        time.sleep(self.retry_delay)
                        continue
                # 如果未连接，短暂休眠后继续
                if not self.connected:
                    time.sleep(0.5)
                    continue

                time.sleep(0.1) # 主循环休眠

            except Exception as e:
                self.status_signal.emit(f"手势识别错误: {e}")
                self.connected = False
                self.sensor_active_signal.emit(False)
                self.stop_udp_sender()  # 出现错误时停止UDP
                time.sleep(self.retry_delay)

        self.cleanup()      # 线程结束时清理资源

    # 新增方法：启动UDP发送线程（只在Myo连接成功后调用）
    def start_udp_sender(self):
        """启动UDP手势发送线程"""
        if not self.udp_active:
            if self.gesture_sender.init_udp():
                # 创建并启动UDP发送线程
                self.sender_thread = threading.Thread(target=self.gesture_sender.run)
                self.sender_thread.daemon = True    # 设置为守护线程
                self.sender_thread.start()
                self.udp_active = True
                self.status_signal.emit("UDP手势发送线程已启动")
            else:
                self.status_signal.emit("警告: UDP初始化失败，无法发送手势")

    # 新增方法：停止UDP发送线程
    def stop_udp_sender(self):
        """停止UDP手势发送线程"""
        if self.udp_active:
            self.gesture_sender.stop()  # 停止发送器
            # 等待线程结束(最多0.5秒)
            if hasattr(self, 'sender_thread') and self.sender_thread.is_alive():
                self.sender_thread.join(0.5)
            self.udp_active = False
            self.status_signal.emit("UDP手势发送已停止")

    def start_connection(self):
        """开始连接设备"""
        self.should_connect = True

    def stop_connection(self):
        """停止连接设备"""
        self.should_connect = False
        self.disconnect_device()

    def connect_device(self):
        try:
            # 只连接Myo设备，UDP在连接成功后单独启动
            return self.myo_classifier.connect()
        except Exception as e:
            self.status_signal.emit(f"连接失败: {e}")
            return False

    def disconnect_device(self):
        """断开设备连接"""
        try:
            # 先停止UDP发送
            self.stop_udp_sender()

            # 然后断开Myo连接
            if self.myo_classifier and self.myo_classifier.connected:
                self.myo_classifier.disconnect()
                self.connected = False
                self.sensor_active_signal.emit(False)
                self.status_signal.emit("Myo设备已断开连接")
                self.should_connect = False
        except:
            pass

    def stop(self):
        """停止线程"""
        self.running = False
        self.disconnect_device()
        self.wait(2000)

    def cleanup(self):
        """清理资源"""
        self.disconnect_device()
        try:
            # 重置手势和传感器数据文件
            with open(GESTURE_FILE, 'w') as f:
                f.write("-1,0.0")
            with open(SENSOR_DATA_FILE, 'w') as f:
                f.write("0 0 0 0 0 0 0 0")
            self.status_signal.emit("文件清理完成")
        except:
            pass
        self.status_signal.emit("手势识别线程已停止")


class MyoClassifier(Myo):
    """Myo设备分类器类，继承自Myo基类"""
    def __init__(self, classifier, mode=emg_mode.PREPROCESSED, hist_len=25):
        """
                初始化Myo分类器
                参数:
                    classifier: KNN分类器实例
                    mode: EMG数据模式
                    hist_len: 历史记录长度
                """
        super().__init__(mode=mode)
        self.classifier = classifier    # KNN分类器
        self.hist_len = hist_len        # 历史记录长度
        self.history = deque([0] * self.hist_len, self.hist_len) # 手势历史队列
        self.history_cnt = np.zeros(10, dtype=np.int32)   # 手势计数数组
        self.last_pose = None                   # 最后识别的手势
        self.last_confidence = 0.0              # 最后识别的置信度
        self.add_emg_handler(self.emg_handler)  # 添加EMG数据处理器
        self.last_print_time = time.time()      # 最后打印时间
        self.connected = False                  # 连接状态
        self.last_classify_time = 0             # 最后分类时间
        self.classify_interval = 0.1            # 分类间隔(秒)
        self.last_emg = None                    # 最后EMG数据
        self.last_written_gesture = -1          # 最后写入的手势
        self.last_written_time = 0              # 最后写入时间
        self.write_interval = 0.3               # 写入间隔(秒)
        self.run_thread = None                  # 运行线程
        self.sensor_write_interval = 0.2        # 传感器数据写入间隔
        self.last_sensor_write_time = 0         # 最后传感器数据写入时间


    def connect(self):
        """连接Myo设备"""
        try:
            super().connect()# 调用父类连接方法
            self.connected = True
            # 创建并启动设备运行线程
            self.run_thread = threading.Thread(target=self.run_thread_func, daemon=True)
            self.run_thread.start()
            self.reset_files()# 重置文件
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.connected = False
            return False

    def reset_files(self):
        """重置手势和传感器数据文件"""
        try:
            with open(GESTURE_FILE, 'w') as f:
                f.write("-1,0.0")
            with open(SENSOR_DATA_FILE, 'w') as f:
                f.write("0 0 0 0 0 0 0 0")
        except:
            pass

    def run_thread_func(self):
        """设备运行线程函数"""
        while self.connected:
            try:
                super().run()# 调用父类运行方法
            except Exception as e:
                print(f"设备运行错误: {e}")
                self.connected = False

    def disconnect(self):
        """断开Myo设备连接"""
        try:
            if self.connected:
                self.connected = False
                # 等待线程结束(最多1秒)
                if self.run_thread and self.run_thread.is_alive():
                    self.run_thread.join(timeout=1.0)
                super().disconnect()# 调用父类断开方法
        except Exception as e:
            print(f"断开连接错误: {e}")
        finally:
            print("Myo设备已断开连接")

    def emg_handler(self, emg, moving):
        # EMG数据处理器
        current_time = time.time()
        try:
            # 确保emg是有效的8维数据
            if not isinstance(emg, (list, np.ndarray)) or len(emg) != 8:
                emg = list(emg)
        except:
            emg = [0] * 8

        self.last_emg = emg # 保存最后EMG数据
        # 定期写入传感器数据到文件
        if current_time - self.last_sensor_write_time >= self.sensor_write_interval:
            try:
                with open(SENSOR_DATA_FILE, 'w') as f:
                    f.write(" ".join(str(int(v)) for v in emg))
                self.last_sensor_write_time = current_time
            except Exception as e:
                print(f"写入传感器数据失败: {e}")
        # 控制分类频率
        if current_time - self.last_classify_time < self.classify_interval: return
        self.last_classify_time = current_time

        try:
            # 1. 使用KNN分类器进行分类
            emg_array = np.array(emg, dtype=np.int32)
            gesture_id, confidence = self.classifier.classify(emg_array)
            # 2. 更新手势历史记录
            oldest = self.history[0]
            self.history_cnt[oldest] = max(0, self.history_cnt[oldest] - 1)
            self.history_cnt[gesture_id] += 1
            self.history.append(gesture_id)
            # 3. 确定当前手势(使用历史计数最多的手势)
            current_pose = np.argmax(self.history_cnt)
            count = self.history_cnt[current_pose]
            # 4. 如果手势变化足够大，更新最后手势
            if (self.last_pose is None or
                    (count > self.history_cnt[self.last_pose] + 3 and count > self.hist_len // 3)):
                self.last_pose = current_pose
                self.last_confidence = confidence
                self.update_gesture_file(current_pose, confidence)
        except Exception as e:
            print(f"分类错误: {e}")

    def update_gesture_file(self, gesture, confidence):
        #更新手势文件 参数:gesture: 手势ID confidence: 置信度
        current_time = time.time()
        # 控制写入频率或手势变化时写入
        if (current_time - self.last_written_time >= self.write_interval or
                gesture != self.last_written_gesture):
            try:
                with open(GESTURE_FILE, 'w') as f:
                    f.write(f"{gesture},{confidence:.2f}")
                self.last_written_gesture = gesture
                self.last_written_time = current_time
            except Exception as e:
                print(f"写入手势文件失败: {e}")

