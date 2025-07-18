#knn_cpp.py
import ctypes
import os
import numpy as np
import time

from config import K
class KNNClassifier:
    def __init__(self, k=K, max_samples=1500, lib_path="core/libknn.so"):
        """
        初始化C++ KNN分类器

        参数:
            k: KNN算法的K值（默认15）
            max_samples: 每个类别加载的最大样本数（默认1500）
            lib_path: C++库的路径（默认"libknn.so"）
        """
        # 获取库的绝对路径
        if not os.path.isabs(lib_path):
            lib_path = os.path.abspath(lib_path)

        print(f"加载KNN共享库: {lib_path}")
        start_time = time.time()

        # 加载共享库
        self.lib = ctypes.CDLL(lib_path)

        # 定义函数原型（指定参数和返回类型）
        # knn_create函数原型：接收int, int参数，返回void指针
        self.lib.knn_create.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.knn_create.restype = ctypes.c_void_p
        # knn_load_data函数原型：接收void指针和字符串路径
        self.lib.knn_load_data.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.knn_load_data.restype = None
        # knn_classify函数原型：接收void指针、uint16数组指针、int指针和float指针
        self.lib.knn_classify.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_float)
        ]
        self.lib.knn_classify.restype = None
        # knn_destroy函数原型：接收void指针
        self.lib.knn_destroy.argtypes = [ctypes.c_void_p]
        self.lib.knn_destroy.restype = None

        # 创建C++对象
        print(f"创建KNN分类器 (k={k}, max_samples={max_samples})")
        self.obj = self.lib.knn_create(k, max_samples)
        if not self.obj:
            raise RuntimeError("Failed to create KNN classifier object")

        load_time = (time.time() - start_time) * 1000
        print(f"KNN初始化完成, 耗时: {load_time:.2f}ms")

    def load_data(self, base_path):
        """从指定目录加载训练数据"""
        if not os.path.exists(base_path):
            raise FileNotFoundError(f"数据目录未找到: {base_path}")

        # 确保路径是绝对路径
        abs_path = os.path.abspath(base_path)
        print(f"从 {abs_path} 加载训练数据...")
        start_time = time.time()
        # 调用C++函数加载数据
        self.lib.knn_load_data(self.obj, abs_path.encode('utf-8'))

        load_time = (time.time() - start_time) * 1000
        print(f"数据加载完成, 耗时: {load_time:.2f}ms")

    def classify(self, emg_data):
        """
        对8维EMG数据进行分类

        参数:
            emg_data: 8维整数数组或列表，EMG传感器数据

        返回:
            (gesture_id, confidence): 手势ID和置信度
        """
        # 输入数据验证和转换
        if isinstance(emg_data, np.ndarray):
            if emg_data.dtype != np.uint16:
                emg_data = emg_data.astype(np.uint16)   # 转换为uint16类型
            if emg_data.ndim != 1 or emg_data.size != 8:
                raise ValueError("输入数组必须是一维且包含8个元素")
        elif isinstance(emg_data, list):
            if len(emg_data) != 8:
                raise ValueError("输入列表必须恰好包含8个元素")
            emg_data = np.array(emg_data, dtype=np.uint16)  # 列表转numpy数组
        else:
            raise TypeError("emg_data 必须是列表或numpy数组")

        # 准备输出变量（通过引用传递）
        prediction = ctypes.c_int()     # 存储预测结果
        confidence = ctypes.c_float()   # 存储置信度

        # 调用C++分类函数
        start_time = time.time()
        self.lib.knn_classify(
            self.obj,   # KNN对象指针
            emg_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),# 输入数据指针
            ctypes.byref(prediction),   # 预测结果引用
            ctypes.byref(confidence)    # 置信度引用
        )
        classify_time = (time.time() - start_time) * 1000

        # 打印性能信息
        print(f"分类完成: 手势={prediction.value}, 置信度={confidence.value:.2f}, 耗时={classify_time:.3f}ms")

        return prediction.value, confidence.value

    def __del__(self):
        """销毁C++对象"""
        if hasattr(self, 'obj') and self.obj:
            print("清理KNN资源...")
            self.lib.knn_destroy(self.obj)