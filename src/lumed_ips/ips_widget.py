"""User Interface (UI) for the control of IPS lasers with the IPSLaser() class 
imported from the laser_control module"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from time import strftime

import pyqt5_fugueicons as fugue
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget

from lumed_ips.ips_control import IpsLaser, LaserInfo
from lumed_ips.ui.ips_ui import Ui_ipsWidget

logger = logging.getLogger(__name__)

LOGS_DIR = Path.home() / "logs/IPS"
LOG_PATH = LOGS_DIR / f"{strftime('%Y_%m_%d_%H_%M_%S')}.log"

LASER_STATE = {0: "Idle", 1: "ON", 2: "Not connected"}
STATE_COLORS = {
    0: "QLabel { background-color : blue; }",
    1: "QLabel { background-color : red; }",
    2: "QLabel { background-color : grey; }",
}

LOG_FORMAT = (
    "%(asctime)s - %(levelname)s"
    "(%(filename)s:%(funcName)s)"
    "(%(filename)s:%(lineno)d) - "
    "%(message)s"
)


def configure_logger():
    """Configures the logger if lumed_ips is launched as a module"""

    if not LOGS_DIR.parent.exists():
        LOGS_DIR.parent.mkdir()
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir()

    formatter = logging.Formatter(LOG_FORMAT)

    terminal_handler = logging.StreamHandler()
    terminal_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(formatter)

    logger.addHandler(terminal_handler)
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)


class IpsLaserWidget(QWidget, Ui_ipsWidget):
    """User Interface for IPS laser control.
    Subclass IpsLaserWidget to customize the Ui_LaserControl widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # logger
        logger.info("Widget intialization")

        self.laser: IpsLaser = IpsLaser()
        self.laser_info: LaserInfo = self.laser.get_info()
        self.last_enabled_state: bool = False

        # ui parameters
        self.setup_default_ui()
        self.connect_ui_signals()
        self.setup_update_timer()
        self.update_ui()
        logger.info("Widget initialization complete")

    def setup_default_ui(self):
        self.pushbtnFindLaser.setIcon(fugue.icon("magnifier-left"))
        self.spinboxLaserCurrent.setMaximum(1500)  # max current of IPS lasers

        self.spinboxPulseDuration.setEnabled(False)
        self.pushbtnPulse.setEnabled(False)

    def connect_ui_signals(self):
        self.pushbtnFindLaser.clicked.connect(self.find_laser)
        self.pushbtnConnect.clicked.connect(self.connect_laser)
        self.pushbtnDisconnect.clicked.connect(self.disconnect_laser)
        self.pushbtnLaserEnable.clicked.connect(self.enable_laser)
        self.pushbtnLaserDisable.clicked.connect(self.disable_laser)
        self.spinboxLaserCurrent.valueChanged.connect(self.set_laser_current)

    def find_laser(self):
        logger.info("Looking for connected lasers")
        self.pushbtnFindLaser.setEnabled(False)
        self.pushbtnFindLaser.setIcon(fugue.icon("hourglass"))
        self.repaint()

        try:
            lasers = self.laser.find_ips_laser()
            logger.info("Found lasers : %s", lasers)
            self.comboboxAvailableLaser.clear()
            for laser in lasers:
                self.comboboxAvailableLaser.addItem(laser)
        except Exception as e:
            logger.error(e, exc_info=True)
        self.pushbtnFindLaser.setEnabled(True)
        self.pushbtnFindLaser.setIcon(fugue.icon("magnifier-left"))
        self.update_ui()

    def connect_laser(self):
        logger.info("Connecting laser")
        self.pushbtnConnect.setEnabled(False)
        try:
            laser_comport = self.comboboxAvailableLaser.currentText()
            self.laser.comport = laser_comport
            self.laser.connect()
            logger.info("Connected laser : %s", laser_comport)
            self.set_initial_configurations()
        except Exception as e:
            logger.error(e, exc_info=True)
        self.update_ui()
        self.update_timer.start()

    def disconnect_laser(self):
        logger.info("Disconnecting laser")
        self.pushbtnDisconnect.setEnabled(False)
        try:
            self.set_initial_configurations()
            self.laser.disconnect()
        except Exception as e:
            logger.error(e, exc_info=True)
        self.update_ui()
        self.update_timer.stop()

    def enable_laser(self):
        logger.info("Enabling laser")
        self.laser.set_enable(True)
        self.last_enabled_state = True
        self.update_ui()

    def disable_laser(self):
        logger.info("Disabling laser")
        self.laser.set_enable(False)
        self.last_enabled_state = False
        self.update_ui()

    def set_laser_current(self):
        laser_current = self.spinboxLaserCurrent.value()
        logger.info("Setting laser current : %s", laser_current)
        self.laser.set_laser_current(laser_current)

    def set_initial_configurations(self):
        logger.info("Setting initial laser configurations")
        logger.info("Setting laser to disable")
        self.laser.set_enable(False)
        logger.info("Setting laser current to 0 mA")
        self.laser.set_laser_current(1)

    def setup_update_timer(self):
        """Creates the PyQt Timer and connects it to the function that updates
        the UI and gets the laser infos."""
        self.update_timer = QTimer()
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self.update_ui)

    def setLabelConnected(self, isconnected: bool) -> None:
        if isconnected:
            self.labelLaserConnected.setText("Connected")
            self.labelLaserConnected.setStyleSheet("color:green")
        else:
            self.labelLaserConnected.setText("Not Connected")
            self.labelLaserConnected.setStyleSheet("color:red")

    def setLabelEnabled(self, isenabled: bool) -> None:
        if isenabled:
            self.labelLaserEnabled.setText("ENABLED")
            self.labelLaserEnabled.setStyleSheet("color:red")
        else:
            self.labelLaserEnabled.setText("Disabled")
            self.labelLaserEnabled.setStyleSheet("color:green")

    def update_ui(self):
        self.updateLaserInfo()

        # Enable/disable controls if laser is connected or not
        is_connected = self.laser_info.is_connected
        self.pushbtnConnect.setEnabled(not is_connected)
        self.comboboxAvailableLaser.setEnabled(not is_connected)
        self.pushbtnFindLaser.setEnabled(not is_connected)
        self.pushbtnDisconnect.setEnabled(is_connected)
        self.groupboxControl.setEnabled(is_connected)
        self.setLabelConnected(is_connected)

        self.pushbtnLaserEnable.setEnabled(not self.laser_info.is_enabled)

    def laser_safety_check(self):
        is_enabled = self.laser_info.is_enabled
        if is_enabled != self.last_enabled_state:
            logger.warning(
                "Laser safety trip setting laser to %s",
                ["Disabled", "Enabled"][is_enabled],
            )
            self.laser.set_enable(is_enabled)
            self.last_enabled_state = is_enabled

    def updateLaserInfo(self):

        self.laser_info = self.laser.get_info()
        self.laser_safety_check()

        # update UI based on laserinfo
        self.setLabelEnabled(self.laser_info.is_enabled)
        self.texteditModel.setPlainText(self.laser_info.model)
        self.texteditSN.setPlainText(self.laser_info.serial_number)
        self.texteditWavelength.setPlainText(str(self.laser_info.wavelength))
        self.texteditCurrent.setPlainText(str(self.laser_info.laser_current))
        self.texteditPower.setPlainText(str(self.laser_info.laser_power))
        self.texteditTemperature.setPlainText(str(self.laser_info.temperature))


if __name__ == "__main__":

    # Set up logging
    configure_logger()

    # Create app window
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    window.setCentralWidget(IpsLaserWidget())

    app.exec_()
