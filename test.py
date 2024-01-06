# -*- coding: utf-8 -*-
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QDateTime, Qt, QTimer, QThread, pyqtSignal, QRect
import time
import asyncqt
from pyqtgraph import PlotWidget
import re
import pyqtgraph as pg


class WT901BT:
    notify_characteristic = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write_characteristic = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    device_addr = "38:1E:C7:E4:78:6C"


class HC04:
    notify_characteristic = "0000ffe4-0000-1000-8000-00805f9b34fb"
    write_characteristic = "0000ffe4-0000-1000-8000-00805f9b34fb"
    device_addr = "C4:22:09:09:03:EC"


# 准备发送的消息，为“hi world\n”的HEX形式（包括回车符0x0A 0x0D）
send_str = bytearray([0x68, 0x69, 0x20, 0x77, 0x6F, 0x72, 0x6C, 0x64, 0x0A, 0x0D])


class myBLE(QMainWindow):
    def __init__(self):
        super(myBLE, self).__init__()
        self.setWindowTitle("蓝牙实时数据显示")
        self.BLE = HC04()

        layout = QHBoxLayout()
        self.button1 = QPushButton("connect")
        self.button1.setText("connect button")
        self.button1.setCheckable(True)
        self.button1.toggle()
        self.button1.clicked.connect(lambda: self.connect_callback())
        layout.addWidget(self.button1, alignment=Qt.AlignTop)

        self.button2 = QPushButton("read_write")
        self.button2.setText("read_write button")
        self.button2.setCheckable(True)
        self.button2.toggle()
        self.button2.clicked.connect(lambda: self.read_write())
        layout.addWidget(self.button2, alignment=Qt.AlignTop)

        self.button3 = QPushButton("close")
        self.button3.setText("close button")
        self.button3.setCheckable(True)
        self.button3.toggle()
        self.button3.clicked.connect(lambda: self.close_callback())
        layout.addWidget(self.button3, alignment=Qt.AlignTop)

        mainFrame = QWidget()
        mainFrame.setLayout(layout)
        self.setCentralWidget(mainFrame)

        pg.setConfigOption("background", "#FFFFFF")
        pg.setConfigOption("foreground", "d")
        self.plotWidget = PlotWidget(mainFrame)
        self.plotWidget.setGeometry(QRect(10, 60, 780, 500))
        self.plotWidget.setObjectName("plotWidget")
        self.plotWidget.showGrid(x=True, y=True, alpha=0.8)
        self.line_array = []
        self.line_array.append(
            self.plotWidget.plot([], pen=pg.mkPen(width=2, color="r"))
        )
        self.CHAR1_DATA = []

        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_plot)

        # self.setLayout(layout)
        self.resize(800, 600)
        self.status = self.statusBar()
        self.status.showMessage("启动成功", 2000)

        self.device = None
        self.toDisconnect = False
        # asyncio.run(self.connect())
        # asyncio.run(self.read_write())

    def connect_callback(self):
        connect_task = self.connect()
        asyncio.ensure_future(connect_task)

    async def connect(self):
        print("starting scan...")
        # 基于MAC地址查找设备
        self.device = await BleakScanner.find_device_by_address(
            self.BLE.device_addr, cb=dict(use_bdaddr=False)
        )
        if self.device is None:
            print("could not find device with address '%s'", self.BLE.device_addr)
            return
        else:
            self.status.showMessage("连接成功", 2000)
            print("connecting to device...")

        def notification_handler(
            characteristic: BleakGATTCharacteristic, data: bytearray
        ):
            print("rev data:", data)

            if "esc" in str(data):
                self.toDisconnect = True
            else:
                tmp = re.findall("\d+\.?\d*", str(data))
                rec = list(map(int, tmp))
                if rec:
                    print("rec: ", rec)
                    self.CHAR1_DATA.extend(rec)
                    while len(self.CHAR1_DATA) > 50:
                        self.CHAR1_DATA.pop(0)

        self.disconnected_event = asyncio.Event()

        def disconnected_callback(client):
            print("Disconnected callback called!")
            self.disconnected_event.set()

        async with BleakClient(
            self.device, disconnected_callback=disconnected_callback
        ) as client:
            print("Connected")
            await client.start_notify(
                self.BLE.notify_characteristic, notification_handler
            )
            self.status.showMessage("开始接收数据", 2000)
            self.timer.start()
            # await asyncio.sleep(100)  # TODO replace this with device loop
            while 1:
                await asyncio.sleep(0.001)  # TODO replace this with device loop
                if self.toDisconnect:
                    break

    async def read_write(self):
        async with BleakClient(self.device) as client:
            await client.write_gatt_char(self.BLE.write_characteristic, send_str)

    def update_plot(self):
        # fast update of all data
        # print("Update plot.")
        self.line_array[0].setData(self.CHAR1_DATA)

    def close_callback(self):
        close_task = self.close()
        asyncio.ensure_future(close_task, loop=loop)

    async def close(self):
        print("close")
        self.status.showMessage("停止接收数据", 2000)
        self.toDisconnect = True
        # self.disconnected_event.set()
        if self.device:
            async with BleakClient(self.device) as client:
                await client.stop_notify(self.BLE.notify_characteristic)
                await client.disconnect()

        app = QApplication.instance()
        # 退出应用程序
        app.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = myBLE()
    win.show()
    # sys.exit(app.exec_())

    loop = asyncqt.QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop
    with loop:
        sys.exit(loop.run_forever())
