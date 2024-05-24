"""User Interface (UI) for the control of IPS lasers with the IPSLaser() class 
imported from the laser_control module"""

import logging
import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget

from laser_control import IpsLaser
from Ui.laser_ui import Ui_LaserControl

LASER_STATE = {0: "Idle", 1: "ON", 2: "Not connected"}
STATE_COLORS = {
    0: "QLabel { color : blue; }",
    1: "QLabel { color : red; }",
    2: "QLabel { color : black; }",
}


class IpsLaserwidget(QWidget, Ui_LaserControl):
    """User Interface for IPS laser control.
    Subclass IpsLaserWidget to customize the Ui_LaserControl widget"""

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.create_logger()
        self.logger.info("Widget intialization")

        self.laser = IpsLaser()
        self.available_lasers = {}

        # ui parameters
        self.setup_signals_slots()
        self.setup_update_timer()
        self.logger.info("Widget launch is done")

    def create_logger(self):
        """Create and setup the logging for the IPS control widget"""
        # create logger
        current_directory = os.getcwd()
        folder_path = os.path.join(current_directory, "logs")
        # Create the folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        LOG_FORMAT = (
            "%(asctime)s - %(levelname)s"
            "(%(filename)s:%(funcName)s)"
            "(%(filename)s:%(lineno)d) - "
            "%(message)s"
        )

        logging.basicConfig(
            filename=os.path.join(folder_path, "logger.log"),
            level=logging.DEBUG,
            format=str(LOG_FORMAT),
            filemode="w",
        )
        self.logger = logging.getLogger("IPSControlLogger")

    def setup_signals_slots(self):
        """Connects the UI buttons and text infos to the IpsLaser() class
        and enables some of the buttons."""
        self.pushButton_update.clicked.connect(self.update_laser_choice)
        self.pushButton_connect.clicked.connect(self.connect_laser)
        self.pushButton_disconnect.clicked.connect(self.disconnect_laser)
        self.spinBox_current.valueChanged.connect(self.update_current)
        self.pushButton_on.clicked.connect(self.enable)
        self.pushButton_off.clicked.connect(self.disable)
        self.pushButton_pulse.clicked.connect(self.pulse)
        self.buttons_enabling(self.laser.status)

    def setup_update_timer(self):
        """Creates the PyQt Timer and connects it to the function that updates
        the UI and gets the laser infos."""
        self.update_timer = QTimer()
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self.update_ui)

    def update_laser_choice(self):
        """Add the devices ports and names to the comboBox that allows laser connection."""
        self.logger.info("Updating the connected devices")
        if self.laser.isconnected is False:
            self.available_lasers = self.laser.find_ips_laser()
            self.comboBox_devices.clear()
            for port, infos in self.available_lasers.items():
                self.comboBox_devices.addItem(f"{port} | {infos['idn']}")
                self.logger.info(
                    "Added device : %s to the comboBox", f"{port} | {infos['idn']}"
                )

    def connect_laser(self):
        """Connects the laser selected in the comboBox."""
        if self.laser.isconnected is False:
            self.logger.info("Trying to connect to a device")
            try:
                self.laser.comport = list(self.available_lasers)[
                    self.comboBox_devices.currentIndex()
                ]
                connected = self.laser.connect()
                if connected == "Success":
                    self.spinBox_current.setProperty("value", 1)  # set current to 1
                    self.update_ui()
                    self.update_timer.start()
                    self.logger.info(
                        "Connection to %s succesfull",
                        list(self.available_lasers)[
                            self.comboBox_devices.currentIndex()
                        ],
                    )
                else:
                    self.logger.warning(
                        "Connection to %s failed. Error messsage : %s",
                        self.available_lasers[self.comboBox_devices.currentIndex()],
                        connected,
                    )
            # catch error if combobox is empty
            except IndexError as e:
                self.logger.warning(
                    "Connection failed. Combobox error : %s, No laser selected.", e
                )

    def disconnect_laser(self):
        """Disconnects the laser that is currently connected"""
        self.logger.info("Trying to disconnect from a device")
        disconnected = self.laser.disconnect()
        if disconnected == "Success":
            self.update_timer.stop()
            self.update_ui()
            self.logger.info("Disconnection succesfull")
        else:
            self.logger.warning(
                "Disconnection failed. Error messsage : %s",
                disconnected,
            )

    def update_current(self):
        """Updates the laser current with the value in the spinBox."""
        if not self.laser.isconnected:
            self.logger.error("Laser not connected")
            return

        self.laser.set_laser_current(self.spinBox_current.value())
        self.logger.info("Laser current set to %d", self.spinBox_current.value())

    def enable(self):
        """Enables the lasing with the laser current selected in the laser current spinBox."""
        if not self.laser.isconnected:
            self.logger.error("Laser not connected")
            return

        self.laser.set_laser_current(self.spinBox_current.value())
        self.laser.enable(1)
        state, _, _ = self.laser.get_enable_state()
        self.logger.info("Lasing enabled, laser enable state: %d", state)

    def disable(self):
        """Disables the lasing."""
        if not self.laser.isconnected:
            self.logger.error("Laser not connected")
            return

        self.laser.set_laser_current(self.spinBox_current.value())
        self.laser.enable(0)
        state, _, _ = self.laser.get_enable_state()
        self.logger.info("Lasing disabled, laser enable state: %d", state)

    def pulse(self):
        """Generates a pulse with the value (in ms) in the pulse duration spinBox."""
        if self.laser.isconnected:
            duration = self.spinBox_pduration.value()
            self.logger.info("Generating pulse of %d ms", duration)
            pulse_timer = QTimer()
            pulse_timer.singleShot(duration, self.disable)
            self.enable()
            pulse_timer.start()

    def update_ui(self):
        """Gets the laser current inforamtions and state and
        updates the laser UI according to them."""
        # laser info
        info_dict = self.laser.get_info()
        self.label_status.setText(LASER_STATE[info_dict["status"]])
        self.label_status.setStyleSheet(STATE_COLORS[info_dict["status"]])
        self.label_current_status.setText(info_dict["current"])
        self.label_power_status.setText(info_dict["power"])
        self.label_temp_status.setText(info_dict["temperature"])
        self.logger.error(info_dict["error"])
        # buttons
        self.buttons_enabling(info_dict["status"])

    def buttons_enabling(self, state: int):
        """Enables and disables the buttons depending on the laser state.

        Parameters : <state> (int) : Laser state : 0: Idle, 1: ON, 2: Not connected
        """
        if state == 2:
            self.enable_new_connections(True)
            self.enable_lasing_buttons(False)
            self.logger.info(
                "Modifying buttons display for laser state : Not connected"
            )
        elif state == 1:
            self.enable_new_connections(False)
            self.enable_lasing_buttons(True)
            self.pushButton_on.setEnabled(False)
            self.pushButton_pulse.setEnabled(False)
            self.logger.info("Modifying buttons display for laser state : ON")
        elif state == 0:
            self.enable_new_connections(False)
            self.enable_lasing_buttons(True)
            self.logger.info("Modifying buttons display for laser state : Idle")

    def enable_lasing_buttons(self, enable: bool):
        """Enables or disable the buttons of the UI related to the lasing.

        Parameters : <enable> (bool) : True to enable, False to disable.
        """
        self.pushButton_on.setEnabled(enable)
        self.pushButton_off.setEnabled(enable)
        self.pushButton_pulse.setEnabled(enable)
        self.spinBox_current.setEnabled(enable)
        self.spinBox_pduration.setEnabled(enable)

    def enable_new_connections(self, enable: bool):
        """Enables or disable the buttons of the UI allowing a new connection.

        Parameters : <enable> (bool) : True to enable, False to disable.
        """
        self.pushButton_connect.setEnabled(enable)
        self.pushButton_update.setEnabled(enable)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    window.setCentralWidget(IpsLaserwidget())

    app.exec_()
