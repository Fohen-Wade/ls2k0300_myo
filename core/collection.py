#collection.py
import os
import struct
import time

import numpy as np
from PyQt5.QtCore import pyqtSignal, QThread

from config import K, SUBSAMPLE, BUFFER_SIZE
from device.pyomyo import emg_mode, Myo


class DataManager(object):
    '''数据管理类，用于存储和分类EMG训练数据'''

    def __init__(self, name="DataManager", color=(0, 200, 0)):
        """
                初始化数据管理器

                参数:
                    name: 管理器名称
                    color: MYOLED显示颜色(RGB)
                """
        self.name = name
        self.color = color
        self.counts = [0] * 10  # 内存计数
        self.data_buffers = [[] for _ in range(10)]  # 每个手势的数据缓冲区

        # 确保所有数据文件存在
        for i in range(10):
            file_path = f'data/vals{i}.dat'
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    pass  # 创建空文件

        self.read_data()

        self.last_store_time = 0
        self.store_interval = 0.02  # 两次存储之间的最小间隔
        self.last_flush_time = time.time()
        self.flush_interval = 1.0  # 每1秒刷新一次缓冲区到文件

    def store_data(self, cls, vals):
        """存储数据到缓冲区，减少文件写入频率"""
        current_time = time.time()

        # 添加到缓冲区
        self.data_buffers[cls].append(vals)
        self.counts[cls] += 1

        # 如果缓冲区满了，或者超过刷新间隔，则写入文件
        if (len(self.data_buffers[cls]) >= BUFFER_SIZE or
                current_time - self.last_flush_time >= self.flush_interval):
            self.flush_buffer(cls)
            self.last_flush_time = current_time

        return True

    def flush_buffer(self, cls):
        """将缓冲区数据写入文件"""
        if not self.data_buffers[cls]:
            return  # 缓冲区为空，无需处理

        # 将缓冲区数据转换为二进制格式
        buffer_data = b''.join(struct.pack('8H', *vals) for vals in self.data_buffers[cls])

        # 写入文件
        with open(f'data/vals{cls}.dat', 'ab') as f:
            f.write(buffer_data)

        # 清空缓冲区
        self.data_buffers[cls] = []

        # 更新训练数据 - 只在有数据时更新
        if self.X.size > 0:
            # 更新训练数据 - 只在有数据时更新
            new_data = np.array(self.data_buffers[cls])
            if new_data.size > 0:
                # 从缓冲区创建新数据数组
                self.train(np.vstack([self.X, new_data]),
                           np.hstack([self.Y, [cls] * len(self.data_buffers[cls])]))

    def read_data(self):
        """从文件读取所有训练数据"""
        X = []# 特征数据列表
        Y = []# 标签列表
        for i in range(10): # 遍历0-9手势
            try:
                file_path = f'data/vals{i}.dat'
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    # 从二进制文件读取数据
                    data = np.fromfile(file_path, dtype=np.uint16)
                    # 确保数据长度正确(8的倍数)
                    if data.size % 8 != 0:
                        data = data[:-(data.size % 8)]
                    if data.size > 0:
                        # 重塑为N×8数组
                        X.append(data.reshape((-1, 8)))
                        # 创建对应的标签数组
                        Y.append(i + np.zeros(X[-1].shape[0]))
                        # 更新内存计数
                        self.counts[i] = X[-1].shape[0]
                    else:
                        X.append(np.empty((0, 8), dtype=np.uint16))
                        Y.append(np.array([]))
                        self.counts[i] = 0
                else:
                    X.append(np.empty((0, 8), dtype=np.uint16))
                    Y.append(np.array([]))
                    self.counts[i] = 0
            except (FileNotFoundError, ValueError):
                X.append(np.empty((0, 8), dtype=np.uint16))
                Y.append(np.array([]))
                self.counts[i] = 0
        # 合并所有数据
        if X:
            self.train(np.vstack(X) if X[0].size > 0 else np.empty((0, 8), dtype=np.uint16),
                       np.hstack(Y) if Y else np.array([]))
        else:
            self.train(np.empty((0, 8), dtype=np.uint16), np.array([]))

    def delete_data(self):
        """删除所有手势数据"""
        for i in range(10):
            file_path = f'data/vals{i}.dat'
            if os.path.exists(file_path):
                os.remove(file_path)
            # 重新创建空文件
            with open(file_path, 'wb') as f:
                pass
            # 重置内存计数和缓冲区
            self.counts[i] = 0
            self.data_buffers[i] = []
        self.read_data()    # 重新读取(空)数据

    def train(self, X, Y):
        """
                更新训练数据

                参数:
                    X: 特征数据(N×8)
                    Y: 标签数据(N)
                """
        self.X = X  # 存储特征
        self.Y = Y  # 存储标签
        self.model = None   # 重置模型


    def nearest(self, d):
        """
                查找最近邻数据点

                参数:
                    d: 查询数据点(8维)

                返回:
                    最近邻的标签
                """
        if self.X.size == 0:
            return 0     # 无数据时返回默认手势
        # 计算欧氏距离
        dists = ((self.X - d) ** 2).sum(1)
        ind = dists.argmin()     # 找到最小距离索引
        return self.Y[ind]       # 返回对应的标签

    def classify(self, d):
        """
          分类EMG数据

          参数:
              d: 要分类的EMG数据(8维)

          返回:
              分类结果(手势ID)
          """
        # 检查是否有足够的数据
        if self.X.size == 0 or self.X.shape[0] < K * SUBSAMPLE:
            return 0 # 数据不足时返回默认手势
        return self.nearest(d)# 使用最近邻分类

    def get_count(self, cls):
        """
        获取指定手势的数据计数

        参数:
            cls: 手势类别(0-9)

        返回:
            该手势的数据数量
        """
        return self.counts[cls]

    def flush_all_buffers(self):
        """将所有缓冲区的数据写入文件"""
        for i in range(10):
            if self.data_buffers[i]:
                self.flush_buffer(i)


class MyoWorker(QThread):
    """Myo设备工作线程(Qt线程)"""
    # 定义信号
    emg_signal = pyqtSignal(tuple, bool)# (emg数据, 是否移动)
    data_stored = pyqtSignal(int)  # 当数据存储时发出手势索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.myo = None     # Myo设备实例
        self.running = False    # 线程运行标志
        self.connected = False  # 设备连接状态
        self.last_process_time = 0  # 最后处理时间
        self.process_interval = 0.02 # 处理间隔(50Hz)

    def connect_myo(self):
        """连接Myo设备"""
        try:
            if not self.myo:
                # 创建Myo实例(预处理模式)
                self.myo = Myo(mode=emg_mode.PREPROCESSED)
            self.myo.connect()  # 连接设备
            self.connected = True
            # 添加EMG数据处理器
            self.myo.add_emg_handler(self.handle_emg)
            return True, "Myo设备已连接"
        except Exception as e:
            return False, f"连接Myo失败: {str(e)}"

    def handle_emg(self, emg, moving):
        """
        EMG数据处理函数(频率控制)

        参数:
            emg: EMG数据(8维)
            moving: 是否移动标志
        """
        current_time = time.time()
        # 控制处理频率
        if current_time - self.last_process_time >= self.process_interval:
            self.emg_signal.emit(tuple(emg), moving) # 发射信号
            self.last_process_time = current_time

    def run(self):
        """线程主函数"""
        if not self.connected:
            return

        self.running = True
        try:
            # 使用Myo的运行方法代替waitForNotifications
            while self.running:
                self.myo.run()      # 处理Myo数据
                time.sleep(0.005)  # 减轻CPU负担
        except Exception as e:
            print(f"Myo工作线程错误: {e}")
        finally:
            self.running = False
            self.connected = False
            if self.myo:
                self.myo.disconnect()   # 断开连接

    def stop(self):
        """停止线程"""
        self.running = False


class EMGHandler(object):
    """EMG数据处理器"""
    def __init__(self, m):
        """
                初始化处理器

                参数:
                    m: 主控制器引用
                """
        self.recording = -1 # 当前记录的手势(-1表示未记录)
        self.m = m          # 主控制器
        self.emg = (0,) * 8 # 当前EMG数据
        self.recording_enabled = True   # 是否启用记录

    def __call__(self, emg, moving):
        """
                处理EMG数据(使实例可调用)

                参数:
                    emg: EMG数据
                    moving: 是否移动标志
        """
        # 如果正在记录且启用记录
        self.emg = emg
        if self.recording >= 0 and self.recording_enabled:
            # 存储数据并通知计数更新
            if self.m.data_manager.store_data(self.recording, emg):
                self.m.update_count(self.recording)