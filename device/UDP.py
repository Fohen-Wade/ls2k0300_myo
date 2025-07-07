#UDP.py
import socket
import time

from config import UDP_IP,UDP_PORT,SEND_FREQ


class GestureSender:
    def __init__(self):
        self.sock = None
        self.running = False
        self.init_udp()

    def init_udp(self):
        """初始化UDP连接"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.running = True
            print(f"UDP初始化完成: {UDP_IP}:{UDP_PORT}")
            return True
        except Exception as e:
            print(f"UDP初始化失败: {e}")
            return False

    def read_gesture(self):
        """从文件读取手势标签"""
        try:
            with open("gesture.txt", "r") as f:
                content = f.read().strip().split(',')
                if len(content) > 0:
                    # 提取手势ID (0-255)
                    gesture_id = int(content[0])

                    # 确保数值在0-255范围内
                    return max(0, min(255, gesture_id))
        except:
            pass
        return 0  # 默认值

    def run(self):
        """运行发送循环"""
        print("启动手势发送线程")
        interval = 1.0 / SEND_FREQ

        while self.running:
            start_time = time.time()

            # 获取当前手势ID
            gesture_id = self.read_gesture()

            # 转换为单个字节
            data_byte = bytes([gesture_id])

            # 发送到ROS
            try:
                self.sock.sendto(data_byte, (UDP_IP, UDP_PORT))
            except Exception as e:
                print(f"UDP发送失败: {e}")

            # 精确控制发送频率
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        """停止发送"""
        self.running = False
        if self.sock:
            self.sock.close()