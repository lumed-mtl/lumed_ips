"""User Interface (UI) for the control of IPS lasers with the IPSLaser class imported from the laser_control module"""
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget

from laser_control import IpsLaser, list_lasers
from Ui.laser_ui import Ui_LaserControl

LASER_STATE = {0: "Idle", 1: "ON", 2: "Not connected"}
STATE_COLORS = {
    0: "QLabel { color : blue; }",
    1: "QLabel { color : red; }",
    2: "QLabel { color : black; }",
}


# Subclass IpsLaserWidget to customize your widget Ui_Form
class IpsLaserwidget(QWidget, Ui_LaserControl):
    """User Interface for laser control"""

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ui parameters
        self.laser = IpsLaser()
        self.update_timer = QTimer()
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self.update_ui)
        self.update_laser_choice()
        self.setup_signals_slots()

    def setup_signals_slots(self):
        """Connects the UI buttons and text infos to the IpsLaserclass()"""
        self.pushButton_update.clicked.connect(self.update_laser_choice)
        self.pushButton_connect.clicked.connect(self.connect_laser)
        self.pushButton_disconnect.clicked.connect(self.disconnect_laser)
        self.spinBox_current.valueChanged.connect(self.update_current)
        self.pushButton_on.clicked.connect(self.enable)
        self.pushButton_off.clicked.connect(self.disable)
        self.pushButton_pulse.clicked.connect(self.pulse)
        self.buttons_enabling(self.laser.status)

    def update_laser_choice(self):
        """Add the devices ports and names to the comboBox"""
        if self.laser.isconnected is False:
            dic_laser = list_lasers()
            self.list_ports = list(dic_laser.keys())
            self.comboBox_devices.clear()
            for port in self.list_ports:
                self.comboBox_devices.addItem(dic_laser[port])

    def connect_laser(self):
        if self.laser.isconnected is False:
            try:
                self.laser.comport = self.list_ports[
                    self.comboBox_devices.currentIndex()
                ]
            except:
                print("No lasers")
            if self.laser.connect() == "Succes":
                self.update_ui()
                self.update_timer.start()
            else:
                print("Connection failed")

    def disconnect_laser(self):
        self.laser.disconnect()
        self.update_timer.stop()
        self.update_ui()

    def update_current(self):
        if self.laser.isconnected:
            self.laser.set_laser_current(self.spinBox_current.value())

    def enable(self):
        if self.laser.isconnected:
            self.laser.set_laser_current(self.spinBox_current.value())
            self.laser.enable(1)

    def disable(self):
        if self.laser.isconnected:
            self.laser.enable(0)

    def pulse(self):
        if self.laser.isconnected:
            duration = self.spinBox_pduration.value()
            success = self.laser.pulse(duration)
            self.label_pulse_info.setText(success)
        else:
            self.label_pulse_info.setText("Not connected")

    def update_ui(self):
        # laser info
        info_dict = self.laser.get_info()
        self.label_status.setText(LASER_STATE[info_dict["status"]])
        self.label_status.setStyleSheet(STATE_COLORS[info_dict["status"]])
        self.label_current_status.setText(info_dict["current"])
        self.label_power_status.setText(info_dict["power"])
        self.label_temp_status.setText(info_dict["temperature"])
        # self.label_error_hardware.setText(info_dict["error"]) #TODO: add error somewhere
        # buttons
        self.buttons_enabling(info_dict["status"])

    def buttons_enabling(self, state: int):
        if state == 2:
            self.enable_new_connections(True)
            self.enable_lasing_buttons(False)
        elif state == 1:
            self.enable_new_connections(False)
            self.enable_lasing_buttons(True)
            self.pushButton_pulse.setEnabled(False)
        elif state == 0:
            self.enable_new_connections(False)
            self.enable_lasing_buttons(True)

    def enable_lasing_buttons(self, enable: bool):
        self.pushButton_on.setEnabled(enable)
        self.pushButton_off.setEnabled(enable)
        self.pushButton_pulse.setEnabled(enable)
        self.spinBox_current.setEnabled(enable)
        self.spinBox_pduration.setEnabled(enable)

    def enable_new_connections(self, enable: bool):
        self.pushButton_connect.setEnabled(enable)
        self.pushButton_update.setEnabled(enable)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    window.setCentralWidget(IpsLaserwidget())

    app.exec_()
