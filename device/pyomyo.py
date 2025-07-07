#pyomyo.py
import enum
import re
import struct
import sys
import threading
import time

import serial
from serial.tools.list_ports import comports

#辅助函数
def pack(fmt, *args):
	"""打包数据为小端字节序"""
	return struct.pack('<' + fmt, *args)

def unpack(fmt, *args):
	"""从小端字节序解包数据"""
	return struct.unpack('<' + fmt, *args)

def multichr(ords):
	"""将整数列表转换为字节串"""
	if sys.version_info[0] >= 3:
		return bytes(ords)
	else:
		return ''.join(map(chr, ords))


def multiord(b):
	"""将字节串转换为整数列表"""
	if sys.version_info[0] >= 3:
		return list(b)
	else:
		return map(ord, b)

class emg_mode(enum.Enum):
	"""EMG数据模式枚举"""
	NO_DATA = 0 # 不发送EMG数据
	PREPROCESSED = 1 # 发送50Hz整流和带通滤波数据
	FILTERED = 2 # 发送200Hz滤波但未整流数据
	RAW = 3 # 发送原始200Hz ADC数据(-128到127)

class Arm(enum.Enum):
	"""手臂位置枚举"""
	UNKNOWN = 0
	RIGHT = 1		# 右臂
	LEFT = 2		# 左臂


class XDirection(enum.Enum):
	"""方向枚举"""
	UNKNOWN = 0
	X_TOWARD_WRIST = 1	# 朝向手腕
	X_TOWARD_ELBOW = 2	# 朝向肘部

#不采用次姿势枚举
class Pose(enum.Enum):
	"""手势姿势枚举"""
	REST = 0
	FIST = 1
	WAVE_IN = 2
	WAVE_OUT = 3
	FINGERS_SPREAD = 4
	THUMB_TO_PINKY = 5
	UNKNOWN = 255


class Packet(object):
	"""蓝牙数据包解析类"""
	def __init__(self, ords):
		self.typ = ords[0]	# 包类型
		self.cls = ords[2]	# 命令类
		self.cmd = ords[3]	# 命令码
		self.payload = multichr(ords[4:])	# 有效载荷

	def __repr__(self):
		return 'Packet(%02X, %02X, %02X, [%s])' % \
			(self.typ, self.cls, self.cmd,
			 ' '.join('%02X' % b for b in multiord(self.payload)))


class BT(object):
	"""实现蓝牙协议的非Myo特定细节"""
	def __init__(self, tty):
		"""初始化蓝牙串口连接"""
		self.ser = serial.Serial(port=tty, baudrate=9600, dsrdtr=1)
		self.buf = []				# 接收缓冲区
		self.lock = threading.Lock()	# 线程锁
		self.handlers = []				# 事件处理器列表

	# internal data-handling methods
	def recv_packet(self):
		"""接收并处理数据包"""
		n = self.ser.inWaiting() # Windows fix	Windows修复

		while True:
			c = self.ser.read()
			if not c:
				return None

			ret = self.proc_byte(ord(c))
			if ret:
				if ret.typ == 0x80:			# BLE事件包
					self.handle_event(ret)
					# Windows修复 - 缓冲区过大时清空
					if n >= 5096:
						print("Clearning",n)
						self.ser.flushInput()
					# End of Windows fix
				return ret

	def proc_byte(self, c):
		"""处理单个字节，构建完整数据包"""
		if not self.buf:
			# 检查包起始字节
			if c in [0x00, 0x80, 0x08, 0x88]:   # BLE/WiFi响应/事件包
				self.buf.append(c)
			return None
		elif len(self.buf) == 1:
			self.buf.append(c)
			# 计算包长度(基础长度+可变长度)
			self.packet_len = 4 + (self.buf[0] & 0x07) + self.buf[1]
			return None
		else:
			self.buf.append(c)

		# 检查是否收到完整包
		if self.packet_len and len(self.buf) == self.packet_len:
			p = Packet(self.buf)
			self.buf = []
			return p
		return None

	def handle_event(self, p):
		"""调用所有注册的事件处理器"""
		for h in self.handlers:
			h(p)

	def add_handler(self, h):
		"""添加事件处理器"""
		self.handlers.append(h)

	def remove_handler(self, h):
		"""移除事件处理器"""
		try:
			self.handlers.remove(h)
		except ValueError:
			pass

	def wait_event(self, cls, cmd):
		"""等待特定事件"""
		res = [None]

		def h(p):
			if p.cls == cls and p.cmd == cmd:
				res[0] = p
		self.add_handler(h)
		while res[0] is None:
			self.recv_packet()
		self.remove_handler(h)
		return res[0]

	# 蓝牙命令实现
	def connect(self, addr):
		"""连接设备"""
		return self.send_command(6, 3, pack('6sBHHHH', multichr(addr), 0, 6, 6, 64, 0))

	def get_connections(self):
		"""获取当前连接"""
		return self.send_command(0, 6)

	def discover(self):
		"""开始扫描设备"""
		return self.send_command(6, 2, b'\x01')

	def end_scan(self):
		"""停止扫描"""
		return self.send_command(6, 4)

	def disconnect(self, h):
		"""断开连接"""
		return self.send_command(3, 0, pack('B', h))

	def read_attr(self, con, attr):
		"""读取属性"""
		self.send_command(4, 4, pack('BH', con, attr))
		return self.wait_event(4, 5)

	def write_attr(self, con, attr, val):
		"""写入属性"""
		self.send_command(4, 5, pack('BHB', con, attr, len(val)) + val)
		return self.wait_event(4, 1)

	def send_command(self, cls, cmd, payload=b'', wait_resp=True):
		"""发送蓝牙命令"""
		s = pack('4B', 0, len(payload), cls, cmd) + payload
		self.ser.write(s)

		while True:
			p = self.recv_packet()
			# no timeout, so p won't be None
			if p.typ == 0:# 响应包
				return p
			# not a response: must be an event非响应包作为事件处理
			self.handle_event(p)


class Myo(object):
	"""实现Myo特定的通信协议"""
	'''Implements the Myo-specific communication protocol.'''

	def __init__(self, tty=None, mode=1):
		"""初始化Myo连接"""
		if tty is None:
			tty = self.detect_tty()		# 自动检测串口
		if tty is None:
			raise ValueError('Myo dongle not found!')

		self.bt = BT(tty)		# 蓝牙实例
		self.conn = None		# 当前连接
		self.emg_handlers = []
		self.imu_handlers = []
		self.arm_handlers = []
		self.pose_handlers = []
		self.battery_handlers = []
		self.mode = mode		# EMG模式

	def detect_tty(self):
		"""检测Myo蓝牙适配器串口"""
		for p in comports():
			if re.search(r'PID=2458:0*1', p[2]):		# Myo适配器的USB PID
				print('using device:', p[0])
				return p[0]

		return None

	def run(self):
		"""主循环，处理接收到的数据包"""
		self.bt.recv_packet()

	def connect(self, addr=None):
		"""连接Myo设备
		地址：Addr is the MAC address in format: [93, 41, 55, 245, 82, 194]"""

		# 清理之前的现有连接
		self.bt.end_scan()
		self.bt.disconnect(0)
		self.bt.disconnect(1)
		self.bt.disconnect(2)

		# 扫描设备
		if (addr is None):
			print('scanning...')
			self.bt.discover()
			while True:
				p = self.bt.recv_packet()
				print('scan response:', p)
				# 检查是否是Myo设备
				if p.payload.endswith(b'\x06\x42\x48\x12\x4A\x7F\x2C\x48\x47\xB9\xDE\x04\xA9\x01\x00\x06\xD5'):
					addr = list(multiord(p.payload[2:8]))
					break
			self.bt.end_scan()
		# 连接设备并等待状态事件
		conn_pkt = self.bt.connect(addr)
		self.conn = multiord(conn_pkt.payload)[-1]
		self.bt.wait_event(3, 0)# 等待连接完成事件

		# 获取固件版本
		fw = self.read_attr(0x17)
		_, _, _, _, v0, v1, v2, v3 = unpack('BHBBHHHH', fw.payload)
		print('firmware version: %d.%d.%d.%d' % (v0, v1, v2, v3))

		self.old = (v0 == 0)# 标记是否为旧固件

		if self.old:
			# 旧固件初始化
			# don't know what these do; Myo Connect sends them, though we get data
			# fine without them
			self.write_attr(0x19, b'\x01\x02\x00\x00')
			# Subscribe for notifications from 4 EMG data channels
			# 订阅4个EMG数据通道
			self.write_attr(0x2f, b'\x01\x00')
			self.write_attr(0x2c, b'\x01\x00')
			self.write_attr(0x32, b'\x01\x00')
			self.write_attr(0x35, b'\x01\x00')

			# 启用EMG数据
			# enable EMG data
			self.write_attr(0x28, b'\x01\x00')
			# 启用IMU数据
			# enable IMU data
			self.write_attr(0x1d, b'\x01\x00')

			# Sampling rate of the underlying EMG sensor, capped to 1000. If it's
			# less than 1000, emg_hz is correct. If it is greater, the actual
			# framerate starts dropping inversely. Also, if this is much less than
			# 1000, EMG data becomes slower to respond to changes. In conclusion,
			# 1000 is probably a good value.f
			# 设置传感器参数
			C = 1000		# EMG传感器采样率上限
			emg_hz = 50		# EMG数据频率
			# strength of low-pass filtering of EMG data
			emg_smooth = 100# EMG低通滤波强度

			imu_hz = 50		# IMU数据频率

			# send sensor parameters, or we don't get any data
			self.write_attr(0x19, pack('BBBBHBBBBB', 2, 9, 2, 1, C, emg_smooth, C // emg_hz, imu_hz, 0, 0))

		else:
			# 新固件初始化
			name = self.read_attr(0x03)
			print('device name: %s' % name.payload)

			# 启用IMU数据
			self.write_attr(0x1d, b'\x01\x00')
			# 启用手臂检测通知
			self.write_attr(0x24, b'\x02\x00')
			# 根据模式启用EMG
			if (self.mode == emg_mode.PREPROCESSED):
				# Send the undocumented filtered 50Hz.
				print("Starting filtered, 0x01")
				self.start_filtered() # 0x01预处理50Hz模式
			elif (self.mode == emg_mode.FILTERED):
				print("Starting raw filtered, 0x02")
				self.start_raw() # 0x02原始滤波200Hz模式
			elif (self.mode == emg_mode.RAW):
				print("Starting raw, unfiltered, 0x03")
				self.start_raw_unfiltered() #0x03原始未滤波模式
			else:
				print("No EMG mode selected, not sending EMG data")
			# Stop the Myo Disconnecting
			# 设置睡眠模式
			self.sleep_mode(1)

			# 启用电池通知
			# enable battery notifications
			self.write_attr(0x12, b'\x01\x10')

		# 添加数据处理器
		# add data handlers
		def handle_data(p):
			"""处理接收到的数据"""
			if (p.cls, p.cmd) != (4, 5):
				return

			c, attr, typ = unpack('BHB', p.payload[:4])
			pay = p.payload[5:]

			# EMG数据处理
			if attr == 0x27:	# 旧固件EMG数据
				# Unpack a 17 byte array, first 16 are 8 unsigned shorts, last one an unsigned char
				vals = unpack('8HB', pay)
				# not entirely sure what the last byte is, but it's a bitmask that
				# seems to indicate which sensors think they're being moved around or
				# something
				emg = vals[:8]		# 8个EMG通道数据
				moving = vals[8]	# 运动标志
				self.on_emg(emg, moving)
			# 新固件EMG数据处理(4个特性)
			# Read notification handles corresponding to the for EMG characteristics
			elif attr == 0x2b or attr == 0x2e or attr == 0x31 or attr == 0x34:
				'''According to http://developerblog.myo.com/myocraft-emg-in-the-bluetooth-protocol/
				each characteristic sends two secuential readings in each update,
				so the received payload is split in two samples. According to the
				Myo BLE specification, the data type of the EMG samples is int8_t.
				'''
				# 每个特性包含2个连续采样(8个int8_t值)
				emg1 = struct.unpack('<8b', pay[:8])
				emg2 = struct.unpack('<8b', pay[8:])
				self.on_emg(emg1, 0)
				self.on_emg(emg2, 0)
			# Read IMU characteristic handle
			# IMU数据处理
			elif attr == 0x1c:
				vals = unpack('10h', pay)
				quat = vals[:4]	# 四元数
				acc = vals[4:7]	# 加速度
				gyro = vals[7:10]	# 陀螺仪
				self.on_imu(quat, acc, gyro)
			# Read classifier characteristic handle
			# 分类器数据处理(手臂/姿势)
			elif attr == 0x23:
				typ, val, xdir, _, _, _ = unpack('6B', pay)

				if typ == 1:  # 戴在手臂上
					self.on_arm(Arm(val), XDirection(xdir))
				elif typ == 2:  #  从手臂移除
					self.on_arm(Arm.UNKNOWN, XDirection.UNKNOWN)
				elif typ == 3:  # 姿势
					self.on_pose(Pose(val))
			# 电池数据处理
			elif attr == 0x11:
				battery_level = ord(pay)
				self.on_battery(battery_level)
			else:
				print('data with unknown attr: %02X %s' % (attr, p))

		self.bt.add_handler(handle_data)

	# 属性读写方法
	def write_attr(self, attr, val):
		"""写入属性"""
		if self.conn is not None:
			self.bt.write_attr(self.conn, attr, val)

	def read_attr(self, attr):
		"""读取属性"""
		if self.conn is not None:
			return self.bt.read_attr(self.conn, attr)
		return None

	def disconnect(self):
		"""断开连接"""
		if self.conn is not None:
			self.bt.disconnect(self.conn)

	# 设备控制方法
	def sleep_mode(self, mode):
		"""设置睡眠模式"""
		self.write_attr(0x19, pack('3B', 9, 1, mode))

	def power_off(self):
		'''
		function to power off the Myo Armband (actually, according to the official BLE specification,
		the 0x04 command puts the Myo into deep sleep, there is no way to completely turn the device off).
		I think this is a very useful feature since, without this function, you have to wait until the Myo battery is
		fully discharged, or use the official Myo app for Windows or Mac and turn off the device from there.
		- Alvaro Villoslada (Alvipe)
		'''
		"""关闭设备(深度睡眠)"""
		self.write_attr(0x19, b'\x04\x00')

	def start_raw(self):
		'''
		Sends 200Hz, non rectified signal.

		To get raw EMG signals, we subscribe to the four EMG notification
		characteristics by writing a 0x0100 command to the corresponding handles.
		'''
		"""启用原始滤波EMG模式(200Hz)"""
		# 订阅4个EMG特性
		self.write_attr(0x2c, b'\x01\x00')  # Suscribe to EmgData0Characteristic
		self.write_attr(0x2f, b'\x01\x00')  # Suscribe to EmgData1Characteristic
		self.write_attr(0x32, b'\x01\x00')  # Suscribe to EmgData2Characteristic
		self.write_attr(0x35, b'\x01\x00')  # Suscribe to EmgData3Characteristic

		'''Bytes sent to handle 0x19 (command characteristic) have the following
		format: [command, payload_size, EMG mode, IMU mode, classifier mode]
		According to the Myo BLE specification, the commands are:
			0x01 -> set EMG and IMU
			0x03 -> 3 bytes of payload
			0x02 -> send 50Hz filtered signals
			0x01 -> send IMU data streams
			0x01 -> send classifier events or dont (0x00)
		'''
		# struct.pack('<5B', 1, 3, emg_mode, imu_mode, classifier_mode)
		self.write_attr(0x19, b'\x01\x03\x02\x01\x01')

		'''Sending this sequence for v1.0 firmware seems to enable both raw data and
		pose notifications.
		'''

		'''By writting a 0x0100 command to handle 0x28, some kind of "hidden" EMG
		notification characteristic is activated. This characteristic is not
		listed on the Myo services of the offical BLE specification from Thalmic
		Labs. Also, in the second line where we tell the Myo to enable EMG and
		IMU data streams and classifier events, the 0x01 command wich corresponds
		to the EMG mode is not listed on the myohw_emg_mode_t struct of the Myo
		BLE specification.
		These two lines, besides enabling the IMU and the classifier, enable the
		transmission of a stream of low-pass filtered EMG signals from the eight
		sensor pods of the Myo armband (the "hidden" mode I mentioned above).
		Instead of getting the raw EMG signals, we get rectified and smoothed
		signals, a measure of the amplitude of the EMG (which is useful to have
		a measure of muscle strength, but are not as useful as a truly raw signal).
		'''

		# self.write_attr(0x28, b'\x01\x00')  # Not needed for raw signals
		# self.write_attr(0x19, b'\x01\x03\x01\x01\x01')

	def start_filtered(self):
		'''
		Sends 50hz filtered and rectified signal.

		By writting a 0x0100 command to handle 0x28, some kind of "hidden" EMG
		notification characteristic is activated. This characteristic is not
		listed on the Myo services of the offical BLE specification from Thalmic
		Labs. Also, in the second line where we tell the Myo to enable EMG and
		IMU data streams and classifier events, the 0x01 command wich corresponds
		to the EMG mode is not listed on the myohw_emg_mode_t struct of the Myo
		BLE specification.
		These two lines, besides enabling the IMU and the classifier, enable the
		transmission of a stream of low-pass filtered EMG signals from the eight
		sensor pods of the Myo armband (the "hidden" mode I mentioned above).
		Instead of getting the raw EMG signals, we get rectified and smoothed
		signals, a measure of the amplitude of the EMG (which is useful to have
		a measure of muscle strength, but are not as useful as a truly raw signal).
		However this seems to use a data rate of 50Hz.
		'''
		"""启用预处理EMG模式(50Hz)"""
		# 启用"隐藏"的EMG特性
		self.write_attr(0x28, b'\x01\x00')
		# 设置EMG模式为预处理(0x01)
		self.write_attr(0x19, b'\x01\x03\x01\x01\x00')

	def start_raw_unfiltered(self):
		'''
		To get raw EMG signals, we subscribe to the four EMG notification
		characteristics by writing a 0x0100 command to the corresponding handles.
		'''
		"""启用原始未滤波EMG模式(200Hz)"""
		self.write_attr(0x2c, b'\x01\x00')  # Suscribe to EmgData0Characteristic
		self.write_attr(0x2f, b'\x01\x00')  # Suscribe to EmgData1Characteristic
		self.write_attr(0x32, b'\x01\x00')  # Suscribe to EmgData2Characteristic
		self.write_attr(0x35, b'\x01\x00')  # Suscribe to EmgData3Characteristic

		# struct.pack('<5B', 1, 3, emg_mode, imu_mode, classifier_mode)
		self.write_attr(0x19, b'\x01\x03\x03\x01\x00')

	def mc_start_collection(self):
		'''Myo Connect sends this sequence (or a reordering) when starting data
		collection for v1.0 firmware; this enables raw data but disables arm and
		pose notifications.
		'''

		self.write_attr(0x28, b'\x01\x00')  # Suscribe to EMG notifications
		self.write_attr(0x1d, b'\x01\x00')  # Suscribe to IMU notifications
		self.write_attr(0x24, b'\x02\x00')  # Suscribe to classifier indications
		self.write_attr(0x19, b'\x01\x03\x01\x01\x01')  # Set EMG and IMU, payload size = 3, EMG on, IMU on, classifier on
		self.write_attr(0x28, b'\x01\x00')  # Suscribe to EMG notifications
		self.write_attr(0x1d, b'\x01\x00')  # Suscribe to IMU notifications
		self.write_attr(0x19, b'\x09\x01\x01\x00\x00')  # Set sleep mode, payload size = 1, never go to sleep, don't know, don't know
		self.write_attr(0x1d, b'\x01\x00')  # Suscribe to IMU notifications
		self.write_attr(0x19, b'\x01\x03\x00\x01\x00')  # Set EMG and IMU, payload size = 3, EMG off, IMU on, classifier off
		self.write_attr(0x28, b'\x01\x00')  # Suscribe to EMG notifications
		self.write_attr(0x1d, b'\x01\x00')  # Suscribe to IMU notifications
		self.write_attr(0x19, b'\x01\x03\x01\x01\x00')  # Set EMG and IMU, payload size = 3, EMG on, IMU on, classifier off

	def mc_end_collection(self):
		'''Myo Connect sends this sequence (or a reordering) when ending data collection
		for v1.0 firmware; this reenables arm and pose notifications, but
		doesn't disable raw data.
		'''

		self.write_attr(0x28, b'\x01\x00')
		self.write_attr(0x1d, b'\x01\x00')
		self.write_attr(0x24, b'\x02\x00')
		self.write_attr(0x19, b'\x01\x03\x01\x01\x01')
		self.write_attr(0x19, b'\x09\x01\x00\x00\x00')
		self.write_attr(0x1d, b'\x01\x00')
		self.write_attr(0x24, b'\x02\x00')
		self.write_attr(0x19, b'\x01\x03\x00\x01\x01')
		self.write_attr(0x28, b'\x01\x00')
		self.write_attr(0x1d, b'\x01\x00')
		self.write_attr(0x24, b'\x02\x00')
		self.write_attr(0x19, b'\x01\x03\x01\x01\x01')

	def vibrate(self, length):
		"""振动"""
		if length in range(1, 4):# 振动长度1-3
			# first byte tells it to vibrate; purpose of second byte is unknown (payload size?)
			self.write_attr(0x19, pack('3B', 3, 1, length))

	def set_leds(self, logo, line):
		"""设置LED颜色"""
		self.write_attr(0x19, pack('8B', 6, 6, *(logo + line)))

	# def get_battery_level(self):
	#     battery_level = self.read_attr(0x11)
	#     return ord(battery_level.payload[5])

	# 数据处理器管理
	def add_emg_handler(self, h):
		"""添加EMG处理器"""
		self.emg_handlers.append(h)

	def add_imu_handler(self, h):
		"""添加IMU处理器"""
		self.imu_handlers.append(h)

	def add_pose_handler(self, h):
		"""添加姿势处理器"""
		self.pose_handlers.append(h)

	def add_arm_handler(self, h):
		"""添加手臂位置处理器"""
		self.arm_handlers.append(h)

	def add_battery_handler(self, h):
		"""添加电池处理器"""
		self.battery_handlers.append(h)

	# 数据回调方法
	def on_emg(self, emg, moving):
		"""EMG数据回调"""
		for h in self.emg_handlers:
			h(emg, moving)

	def on_imu(self, quat, acc, gyro):
		"""IMU数据回调"""
		for h in self.imu_handlers:
			h(quat, acc, gyro)

	def on_pose(self, p):
		"""姿势回调"""
		for h in self.pose_handlers:
			h(p)

	def on_arm(self, arm, xdir):
		"""手臂位置回调"""
		for h in self.arm_handlers:
			h(arm, xdir)

	def on_battery(self, battery_level):
		"""电池电量回调"""
		for h in self.battery_handlers:
			h(battery_level)

if __name__ == '__main__':
	m = Myo(sys.argv[1] if len(sys.argv) >= 2 else None, mode=emg_mode.RAW)

	def proc_emg(emg, moving, times=[]):
		print(emg)

	m.add_emg_handler(proc_emg)
	m.connect()

	m.add_arm_handler(lambda arm, xdir: print('arm', arm, 'xdir', xdir))
	m.add_pose_handler(lambda p: print('pose', p))
	# m.add_imu_handler(lambda quat, acc, gyro: print('quaternion', quat))
	m.sleep_mode(1)
	m.set_leds([128, 128, 255], [128, 128, 255])  # purple logo and bar LEDs
	m.vibrate(1)

	try:
		while True:
			m.run()

	except KeyboardInterrupt:
		m.disconnect()
		quit()
