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
import logging
import contextlib


class WT901BT:
    notify_characteristic = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write_characteristic = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    device_addr = "38:1E:C7:E4:78:6C"
    device_name = "WT901BT"


class HC04:
    notify_characteristic = "0000ffe4-0000-1000-8000-00805f9b34fb"
    write_characteristic = "0000ffe4-0000-1000-8000-00805f9b34fb"
    device_addr = "C4:22:09:09:03:EC"
    device_name = "HC-04SPP"


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
        self.line_array.append(
            self.plotWidget.plot([], pen=pg.mkPen(width=2, color="b"))
        )
        self.CHAR1_DATA = []
        self.CHAR2_DATA = []

        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_plot)

        # self.setLayout(layout)
        self.resize(800, 600)
        self.status = self.statusBar()
        self.status.showMessage("启动成功", 2000)

        self.device = []
        self.client = []
        self.toDisconnect = False

    def connect_callback(self):
        self.connect_task = self.connect2()
        asyncio.ensure_future(self.connect_task)

    async def connect2(self):
        lock = asyncio.Lock()
        connects = [
            asyncio.create_task(self.connect_to_device(lock, i)) for i in range(2)
        ]
        done, pending = await asyncio.wait(connects)
        print(f"Done task count: {len(done)}")
        print(f"Pending task count: {len(pending)}")

    async def connect_to_device(self, lock: asyncio.Lock, device_num: int):
        logging.info("starting device %d task", device_num)
        try:
            async with contextlib.AsyncExitStack() as stack:
                # Trying to establish a connection to two devices at the    same time
                # can cause errors, so use a lock to avoid this.
                async with lock:
                    logging.info("scanning for device %d", device_num)
                    if device_num == 0:
                        name_or_address = WT901BT.device_addr
                        notify_uuid = WT901BT.notify_characteristic
                    elif device_num == 1:
                        name_or_address = HC04.device_addr
                        notify_uuid = HC04.notify_characteristic
                    else:
                        logging.info("unknown device %d", device_num)
                        return
                    device = await BleakScanner.find_device_by_address(name_or_address)

                    logging.info("stopped scanning for %s", name_or_address)

                    if device is None:
                        logging.error("%s not found", name_or_address)
                        return

                    client = BleakClient(device)

                    logging.info("connecting to %s", name_or_address)

                    await stack.enter_async_context(client)

                    logging.info("connected to %s", name_or_address)

                    # This will be called immediately before client.    __aexit__ when
                    # the stack context manager exits.
                    stack.callback(
                        logging.info, "disconnecting from %s", name_or_address
                    )

                # The lock is released here. The device is still connected  and the
                # Bluetooth adapter is now free to scan and connect another     device
                # without disconnecting this one.

                def callback(_, data):
                    logging.info("%s received %r", name_or_address, data)
                    if "esc" in str(data):
                        self.toDisconnect = True
                    else:
                        tmp = re.findall("\d+\.?\d*", str(data))
                        rec = list(map(int, tmp))
                        if rec:
                            if device_num == 0:
                                self.CHAR1_DATA.extend(rec)
                                while len(self.CHAR1_DATA) > 50:
                                    self.CHAR1_DATA.pop(0)
                            if device_num == 1:
                                self.CHAR2_DATA.extend(rec)
                                while len(self.CHAR2_DATA) > 50:
                                    self.CHAR2_DATA.pop(0)

                await client.start_notify(notify_uuid, callback)
                self.timer.start()
                # await asyncio.sleep(1000.0)
                while 1:
                    await asyncio.sleep(0.001)  # TODO replace this with device loop
                    if self.toDisconnect:
                        break
                await client.stop_notify(notify_uuid)
                await client.disconnect()

            # The stack context manager exits here, triggering  disconnection.

            logging.info("disconnected from %s", name_or_address)

        except Exception:
            logging.exception("error with %s", name_or_address)

    async def connect(self):
        logging.info("starting scan...")
        # 基于MAC地址查找设备
        self.device = await BleakScanner.find_device_by_address(
            self.BLE.device_addr, cb=dict(use_bdaddr=False)
        )
        if self.device is None:
            logging.info(
                "could not find device with address '%s'", self.BLE.device_addr
            )
            return
        else:
            self.status.showMessage("连接成功", 2000)
            logging.info("connecting to device...")

        def notification_handler(
            characteristic: BleakGATTCharacteristic, data: bytearray
        ):
            logging.info("rev data:", data)

            if "esc" in str(data):
                self.toDisconnect = True
            else:
                tmp = re.findall("\d+\.?\d*", str(data))
                rec = list(map(int, tmp))
                if rec:
                    logging.info("rec: ", rec)
                    self.CHAR1_DATA.extend(rec)
                    while len(self.CHAR1_DATA) > 50:
                        self.CHAR1_DATA.pop(0)

        self.disconnected_event = asyncio.Event()

        def disconnected_callback(client):
            logging.info("Disconnected callback called!")
            self.disconnected_event.set()

        async with BleakClient(
            self.device, disconnected_callback=disconnected_callback
        ) as client:
            logging.info("Connected")
            await client.start_notify(
                self.BLE.notify_characteristic, notification_handler
            )
            self.status.showMessage("开始接收数据", 2000)
            self.timer.start()
            # await asyncio.sleep(100)  # TODO replace this with device loop

    async def read_write(self):
        async with BleakClient(self.device) as client:
            await client.write_gatt_char(self.BLE.write_characteristic, send_str)

    def update_plot(self):
        self.line_array[0].setData(self.CHAR1_DATA)
        self.line_array[1].setData(self.CHAR2_DATA)

    def close_callback(self):
        close_task = self.close()
        asyncio.ensure_future(close_task)

    async def close(self):
        logging.info("close")
        self.status.showMessage("停止接收数据", 2000)
        self.toDisconnect = True

        # self.disconnected_event.set()
        # if self.device:
        #     async with BleakClient(self.device) as client:
        #         await client.stop_notify(self.BLE.notify_characteristic)
        #         await client.disconnect()

        # app = QApplication.instance()
        # # 退出应用程序
        # app.quit()


if __name__ == "__main__":
    log_level = logging.INFO  # if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    app = QApplication(sys.argv)
    win = myBLE()
    win.show()
    # sys.exit(app.exec_())

    loop = asyncqt.QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop
    with loop:
        sys.exit(loop.run_forever())
