import time
import math
import socket
from collections import defaultdict
from kuavo_humanoid_sdk import KuavoSDK, KuavoRobot, KuavoRobotState, DexterousHand
from kuavo_humanoid_sdk.interfaces.data_types import KuavoPose, KuavoManipulationMpcFrame

# 初始化机器人
if not KuavoSDK().Init(log_level='INFO'):
    print("Init KuavoSDK failed, exit!")
    exit(1)

robot = KuavoRobot()
dex_hand = DexterousHand()

# UDP配置
UDP_IP = "192.168.85.32"
UDP_PORT = 8888
WINDOW_SIZE = 10  # 手势判断窗口大小

def raise_arms(height=0.8):
    """抬起双臂到指定高度"""

    # 只使用左手
    robot.control_robot_end_effector_pose(KuavoPose(position=[0.4, 0.4, 1.25], orientation=[0, 0.9848, 0, 0.1736]), KuavoPose(position=[0, -0.3, 0.5], orientation=[0, 0, 0, 1]), KuavoManipulationMpcFrame.WorldFrame)

def reset_position():
    """复位机器人姿势"""
    print("\n程序结束，复位中...")
    robot.manipulation_mpc_reset()
    robot.arm_reset()
    dex_hand.open()  # 打开双手
    time.sleep(2)
    print("复位完成")

def gesture_control():
    """手势控制主循环"""
    data_counter = defaultdict(int)
    received_count = 0
    last_gesture = None
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    try:
        print("等待手势指令...")
        while True:
            data, _ = sock.recvfrom(1)
            if not data:
                continue
                
            # 统计手势数据
            data_counter[data] += 1
            received_count += 1
            print(f"接收: {data} (计数: {received_count}/{WINDOW_SIZE})")
            
            # 每WINDOW_SIZE次判断一次
            if received_count >= WINDOW_SIZE:
                # 找出最多出现的手势
                gesture = max(data_counter.items(), key=lambda x: x[1])[0]
                print(f"检测到手势: {gesture}")
                
                # 只有手势变化时才执行
                if gesture != last_gesture:
                    execute_gesture(gesture)
                    last_gesture = gesture
                
                # 重置计数器
                data_counter.clear()
                received_count = 0
                
    except KeyboardInterrupt:
        print("\n用户中断程序")
    finally:
        sock.close()
        reset_position()

def execute_gesture(gesture):
    """执行对应手势和手臂动作"""
    # 先抬起手臂
    raise_arms()
    
    # 根据手势执行不同动作
    # 根据接收到的字节数据执行不同的手势
    if gesture == b'\x00':
        print("执行手势0 - 握拳")
        dex_hand.make_gesture(l_gesture_name="fist", r_gesture_name="none")
    elif gesture == b'\x01':
        print("执行手势1 - 食指指")
        dex_hand.make_gesture(l_gesture_name="number_1", r_gesture_name="none")
    elif gesture == b'\x02':
        print("执行手势2 - 哦也")
        dex_hand.make_gesture(l_gesture_name="victory", r_gesture_name="none")
    elif gesture == b'\x03':
        print("执行手势3 - OK")
        dex_hand.make_gesture(l_gesture_name="ok", r_gesture_name="none")
    elif gesture == b'\x04':
        print("执行手势4 - 数字四")
        dex_hand.make_gesture(l_gesture_name="number_4", r_gesture_name="none")
    elif gesture == b'\x05':
        print("执行手势5 - 松弛")
        dex_hand.make_gesture(l_gesture_name="none", r_gesture_name="none")
    elif gesture == b'\x06':
        print("执行手势6 - 点赞")
        dex_hand.make_gesture(l_gesture_name="thumbs-up", r_gesture_name="none")
    elif gesture == b'\x07':
        print("执行手势7 - 数字7")
        dex_hand.make_gesture(l_gesture_name="number_7", r_gesture_name="none")
    elif gesture == b'\x08':
        print("执行手势8 - 摇滚")
        dex_hand.make_gesture(l_gesture_name="rock-and-roll", r_gesture_name="none")
    else:
        print(f"收到未知字节: {gesture} - 执行默认操作(双手张开)")
        dex_hand.open()  # 默认打开双手
    print("操作执行完毕\n")
if __name__ == "__main__":
    try:
        # 初始站立姿势
        robot.stance()
        if not KuavoRobotState().wait_for_stance():
            print("进入站立姿势失败!")
            exit(1)
            
        print("机器人已就位，开始手势控制...")
        gesture_control()
        
    except Exception as e:
        print(f"程序异常: {e}")
    finally:
        reset_position()