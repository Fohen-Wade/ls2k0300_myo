# config.py

# 文件路径配置
GESTURE_FILE = "gesture.txt"          # 手势数据文件
SENSOR_DATA_FILE = "sensor_data.txt"  # 传感器数据文件

# Myo设备配置
MYO_CONNECTION_TIMEOUT = 10           # 连接超时(秒)
MYO_SAMPLING_RATE = 50                # 采样率(Hz)

# 分类器参数
K = 15                             # KNN的K值
SUBSAMPLE = 3                         # 降采样系数

#UDP参数
UDP_IP = "192.168.85.32"  # ROS主机IP
UDP_PORT = 8888  # ROS主机端口
SEND_FREQ = 10.0  # 发送频率(Hz) - 10Hz

#数据缓冲区
BUFFER_SIZE = 20  # 缓冲20个数据点后再写入文件