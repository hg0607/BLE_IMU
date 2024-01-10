# -*- coding: utf-8 -*-
import asyncio
from bleak import BleakClient, BleakScanner
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import pyqtgraph as pg
from pyqtgraph import PlotWidget
import sys, os
import time
import asyncqt
import re
import logging
import contextlib


class WT901DCL:
    notify_uuid = "0000ffe4-0000-1000-8000-00805f9a34fb"
    write_uuid = "0000ffe9-0000-1000-8000-00805f9a34fb"
    name = ["WTwisemen01", "WTwisemen02"]
    address = ["C4:AB:FC:25:36:E1", "D4:65:BA:0A:3B:47"]


class BLE_IMU(QMainWindow):
    def __init__(self):
        super(BLE_IMU, self).__init__()
        self.setWindowTitle("蓝牙IMU数据实时显示")

        layout = QHBoxLayout()
        self.button1 = QPushButton("connect")
        self.button1.setText("connect button")
        self.button1.setCheckable(True)
        self.button1.toggle()
        self.button1.clicked.connect(lambda: self.connect_callback())
        layout.addWidget(self.button1, alignment=Qt.AlignTop)

        self.button2 = QPushButton("close")
        self.button2.setText("close button")
        self.button2.setCheckable(True)
        self.button2.toggle()
        self.button2.clicked.connect(lambda: self.close_callback())
        layout.addWidget(self.button2, alignment=Qt.AlignTop)

        mainFrame = QWidget()
        mainFrame.setLayout(layout)
        self.setCentralWidget(mainFrame)

        pg.setConfigOption("background", "#FFFFFF")
        pg.setConfigOption("foreground", "d")
        self.plotWidget = PlotWidget(mainFrame)
        self.plotWidget.setGeometry(QRect(10, 60, 780, 500))
        self.plotWidget.setObjectName("plotWidget")
        self.plotWidget.showGrid(x=True, y=True, alpha=0.8)
        self.plotWidget.addLegend()
        self.line_array = []
        self.line_array.append(
            self.plotWidget.plot([], pen=pg.mkPen(width=2, color="r"), name="IMU1_ANGX")
        )
        self.line_array.append(
            self.plotWidget.plot([], pen=pg.mkPen(width=2, color="g"), name="IMU1_ANGY")
        )
        self.line_array.append(
            self.plotWidget.plot([], pen=pg.mkPen(width=2, color="b"), name="IMU1_ANGZ")
        )
        self.line_array.append(
            self.plotWidget.plot(
                [],
                pen=pg.mkPen(width=2, color="r", style=Qt.DashLine, name="IMU2_ANGX"),
            )
        )
        self.line_array.append(
            self.plotWidget.plot(
                [],
                pen=pg.mkPen(width=2, color="g", style=Qt.DashLine, name="IMU2_ANGY"),
            )
        )
        self.line_array.append(
            self.plotWidget.plot(
                [],
                pen=pg.mkPen(width=2, color="b", style=Qt.DashLine, name="IMU2_ANGZ"),
            )
        )
        self.MAXLEN = 1000
        self.IMU_ANG = [[], [], [], [], [], []]

        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.update_plot)

        self.resize(800, 600)
        self.status = self.statusBar()
        self.status.showMessage("启动成功", 2000)

        self.toDisconnect = False

    def connect_callback(self):
        async def connect2():
            async def connect_to_device(lock: asyncio.Lock, device_num: int):
                logging.info("starting device %d task", device_num)
                try:
                    async with contextlib.AsyncExitStack() as stack:
                        # Trying to establish a connection to two devices at the    same time
                        # can cause errors, so use a lock to avoid this.
                        async with lock:
                            logging.info("scanning for device %d", device_num)
                            notify_uuid = WT901DCL.notify_uuid
                            name_or_address = WT901DCL.address[device_num]
                            device = await BleakScanner.find_device_by_address(
                                name_or_address
                            )
                            logging.info("stopped scanning for %s", name_or_address)
                            if device is None:
                                logging.error("%s not found", name_or_address)
                                return

                            client = BleakClient(device)
                            logging.info("connecting to %s", name_or_address)
                            await stack.enter_async_context(client)
                            logging.info("connected to %s", name_or_address)

                            # This will be called immediately before client.__aexit__ when
                            # the stack context manager exits.
                            stack.callback(
                                logging.info, "disconnecting from %s", name_or_address
                            )

                        # The lock is released here. The device is still connected and the
                        # Bluetooth adapter is now free to scan and connect another device
                        # without disconnecting this one.

                        def callback(_, data):
                            logging.info(
                                "%s received %d bytes, %r",
                                name_or_address,
                                len(data),
                                data,
                            )
                            for i in range(len(data) - 19):
                                if data[i] == 0x55 and data[i + 1] == 0x61:
                                    ANGX = (
                                        int.from_bytes(
                                            bytearray([data[i + 14], data[i + 15]]),
                                            sys.byteorder,
                                            signed=True,
                                        )
                                        * 180
                                        / 32768
                                    )

                                    ANGY = (
                                        int.from_bytes(
                                            bytearray([data[i + 16], data[i + 17]]),
                                            sys.byteorder,
                                            signed=True,
                                        )
                                        * 180
                                        / 32768
                                    )

                                    ANGZ = (
                                        int.from_bytes(
                                            bytearray([data[i + 18], data[i + 19]]),
                                            sys.byteorder,
                                            signed=True,
                                        )
                                        * 180
                                        / 32768
                                    )

                                    print(
                                        f"{name_or_address} ANGX = {ANGX}, ANGY = {ANGY}, ANGZ = {ANGZ}"
                                    )
                                    if device_num == 0:
                                        self.IMU_ANG[0].append(ANGX)
                                        self.IMU_ANG[1].append(ANGY)
                                        self.IMU_ANG[2].append(ANGZ)
                                    if device_num == 1:
                                        self.IMU_ANG[3].append(ANGX)
                                        self.IMU_ANG[4].append(ANGY)
                                        self.IMU_ANG[5].append(ANGZ)
                                    for k in range(6):
                                        while len(self.IMU_ANG[k]) > self.MAXLEN:
                                            self.IMU_ANG[k].pop(0)

                        await client.start_notify(notify_uuid, callback)
                        if not self.timer.isActive():
                            self.timer.start()
                        # await asyncio.sleep(1000.0)
                        while 1:
                            await asyncio.sleep(
                                0.001
                            )  # TODO replace this with device loop
                            if self.toDisconnect:
                                break
                        await client.stop_notify(notify_uuid)
                        await client.disconnect()

                    # The stack context manager exits here, triggering  disconnection.

                    logging.info("disconnected from %s", name_or_address)

                except Exception:
                    logging.exception("error with %s", name_or_address)

            lock = asyncio.Lock()
            await asyncio.gather(*(connect_to_device(lock, i) for i in range(2)))

        connect_task = connect2()
        asyncio.ensure_future(connect_task)

    def update_plot(self):
        for i in range(6):
            self.line_array[i].setData(self.IMU_ANG[i])

    def close_callback(self):
        logging.info("close")
        self.status.showMessage("停止接收数据", 2000)
        self.toDisconnect = True


if __name__ == "__main__":
    log_level = logging.INFO  # if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    app = QApplication(sys.argv)
    win = BLE_IMU()
    win.show()
    # sys.exit(app.exec_())

    loop = asyncqt.QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop
    with loop:
        sys.exit(loop.run_forever())
