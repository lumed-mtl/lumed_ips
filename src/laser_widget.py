import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from laser_control import IpsLaser, list_lasers
from Ui.laser_ui import Ui_LaserControl

# TODO : check pulse and on button (fct in resync_ui), same for laser controls and connect disconnect


# Subclass IpsLaserWidget to customize your widget Ui_Form
class IpsLaserwidget(QWidget, Ui_LaserControl):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ui parameters
        self.laser = IpsLaser()
        self.update_timer = QTimer()
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self.resync_ui)
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

    def update_laser_choice(self):  # TODO: remove all and add
        """Add the devices ports and names to the comboBox"""
        if self.laser.isconnected == False:
            dic_laser = list_lasers()
            self.list_ports = list(dic_laser.keys())
            for port in self.list_ports:
                self.comboBox_devices.addItem(dic_laser[port])

    def connect_laser(self):
        if self.laser.isconnected == False:
            try:
                self.laser.comport = self.list_ports[
                    self.comboBox_devices.currentIndex()
                ]
            except:
                print("No lasers")
            if self.laser.connect() == "Succes":
                self.laser.set_laser_current(self.spinBox_current.value())
                self.resync_ui()
                self.update_timer.start()
            else:
                print("Connection failed")

    def disconnect_laser(self):
        self.laser.disconnect()
        self.update_timer.stop()
        self.resync_ui()

    def update_current(self):
        if self.laser.isconnected:
            self.laser.set_laser_current(self.spinBox_current.value())

    def enable(self):
        if self.laser.isconnected:
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

    def resync_ui(self):
        info_dict = self.laser.get_info()
        self.label_status.setText(info_dict["status"])
        self.label_current_status.setText(info_dict["current"])
        self.label_power_status.setText(info_dict["power"])
        self.label_temp_status.setText(info_dict["temperature"])
        # self.label_error_hardware.setText(info_dict["error"]) #TODO: add error somewhere

        # display color status
        status_colors = {
            "ON": "QLabel { color : red; }",
            "connected": "QLabel { color : blue; }",
            "not connected": "QLabel { color : black; }",
        }
        self.label_status.setStyleSheet(status_colors[info_dict["status"]])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    window.setCentralWidget(IpsLaserwidget())

    app.exec_()
