#main.py
"""
应用程序主入口模块

该模块是肌电控制仿生手系统的启动入口，负责：
1. 初始化Qt应用程序
2. 设置高DPI缩放以适应高分辨率屏幕
3. 创建并显示主窗口
4. 启动应用程序事件循环
"""
import sys

from PyQt5 import QtWidgets, QtCore

from GUI.main_window import EMGControlGUI

if __name__ == "__main__":
    # 启用高DPI缩放 - 使界面在高分辨率屏幕上显示正常
    # AA_EnableHighDpiScaling是Qt的高DPI缩放属性
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    # 创建QApplication实例 - 每个Qt GUI应用都需要一个QApplication对象
    # sys.argv用于传递命令行参数
    app = QtWidgets.QApplication(sys.argv)
    # 设置应用程序样式为Fusion - 这是一个跨平台的美观样式
    # Fusion样式在所有平台上看起来基本一致
    app.setStyle("Fusion")
    # 创建主窗口实例
    window = EMGControlGUI()
    # 显示主窗口
    window.show()
    # 进入应用程序主事件循环
    # app.exec_()启动事件循环并返回退出状态码
    # sys.exit()确保应用程序完全退出
    sys.exit(app.exec_())