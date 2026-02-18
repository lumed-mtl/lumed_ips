"""Module to control IPS laser by comunnicating in serial with pyvisa."""

import importlib.metadata
import logging
import math
import re
from dataclasses import dataclass
from threading import Lock

import pyvisa

logger = logging.getLogger()

ERROR_CODES = {
    0: "NO_ERROR",  # Hardware error
    3011: "HOUSEKEEPING",  # Hardware error
    3012: "FLASH_INITIALIZATION_FAILED",  # Hardware error
    3013: "FLASH_HOUSEKEEPING_FAILED",  # Hardware error
    3014: "LOW_VOLTAGE_EVENT",  # Hardware error
    3015: "BAD_VOLTAGE_3V3",  # Hardware error
    3016: "BAD_VOLTAGE_VIN",  # Hardware error
    3017: "BAD_VOLTAGE_VTEC",  # Hardware error
    3018: "HIGH_INPUT_CURRENT",  # Hardware error
    3019: "TEC_UPDT_ON_BRD_STATE_BAD",  # Hardware error
    3020: "TEC_UPDT_ON_TEMP_LONG_BAD",  # Hardware error
    3021: "TEC_UPDT_ON_TEMP_OUT_SETPT",  # Hardware error
    3022: "TEC_UPDT_ON_TEMP_OUT_RANGE",  # Hardware error
    3097: "FAILED_INITIAL_POST",  # Hardware error
    3098: "FLASH_PARAMS_REINITIALIZED",  # Hardware error
    3099: "UNIDENTIFIED_ERROR",  # Hardware error
    -102: "Syntax error",  # Communication error
    -103: "Invalid separator",  # Communication error
    -108: "Parameter not allowed",  # Communication error
    -109: "Missing parameter",  # Communication error
    -113: "Undefined header",  # Communication error
    -131: "Invalid suffix",  # Communication error
    -138: "Suffix not allowed",  # Communication error
    -200: "Execution error",  # Communication error
    -224: "Illegal parameter value",  # Communication error
}

STATUS = {
    0: "unknown state",
    1: "board passed POST",
    2: "board failed POST",
    3: "board in normal state",
    4: "board in fault state",
    5: "board in boot load state",
    6: "board not attached",
}


def str2float(string: str) -> float:
    """
    str2float parses a string that may contain units and whitespaces to a float
    using regular expression

    ex:
        str2float("12kg") -> 12
        str2float("3.14 m") -> 3.14
        str2float("784nm") -> 784

    :param string: the string to parse
    :type string: str
    :return: the parsed float
    :rtype: float
    """
    pattern = r"^\s*(-?\d+(\.\d+)?)\s*(\w+)?\s*$"
    match = re.match(pattern, string.strip())
    if match:
        number = float(match.group(1))
    else:
        number = math.nan

    return float(number)


@dataclass
class IPSInfo:
    model: str = ""
    serial_number: str = ""
    is_connected: bool = False
    is_enabled: bool = False
    wavelength: float = float("nan")
    temperature: float = float("nan")
    laser_current: float = float("nan")
    laser_target_current: float = float("nan")
    laser_power: float = float("nan")
    lumed_ips_v: str = importlib.metadata.version("lumed_ips")


class IpsLaser:
    """Control IPS Dual Laser."""

    def __init__(self) -> None:
        self.idn: str | None = None
        self.comport: str | None = None
        self.pyvisa_serial: pyvisa.resources.serial.SerialInstrument | None = (
            None
        )

        self._mutex: Lock = Lock()
        self.isconnected: bool = False
        self.isenabled: bool = False
        self.target_current: int = 0
        self.ressource_manage = pyvisa.ResourceManager("@py")
        self.info = IPSInfo()

    # Device lookup methods

    def find_serial_devices(self) -> dict[str, pyvisa.highlevel.ResourceInfo]:
        """
        Return serial resources likely to include USB CDC ACM and USB-serial devices.

        On Linux these commonly appear as:
          - ASRL/dev/ttyACM*::INSTR
          - ASRL/dev/ttyUSB*::INSTR
        """
        rm = self.ressource_manage

        # First: try common Linux patterns
        resources = {}
        for pattern in (
            "?*ttyACM?*::INSTR",
            "?*ttyUSB?*::INSTR",
            "?*ACM?*",
            "?*USB?*",
        ):
            try:
                resources.update(rm.list_resources_info(query=pattern))
            except Exception as e:
                logger.debug("list_resources_info(%r) failed: %s", pattern, e)

        # Fallback: any ASRL device (covers non-Linux naming like ASRL3::INSTR)
        if not resources:
            try:
                resources.update(rm.list_resources_info(query="ASRL?*"))
            except Exception as e:
                logger.debug("list_resources_info('ASRL?*') failed: %s", e)

        return resources

    def find_ips_laser(
        self,
        *,
        baud_rate: int = 115200,
        timeout_ms: int = 250,
        probe_delay_s: float = 0.05,
        idn_query: str = "*IDN?",
        match_substring: str = "IPS",
    ) -> dict[str, dict]:
        """
        Find IPS lasers available for connection through the pyvisa ResourceManager.

        Returns a dict: {resource_name: {"ressourceInfo": ResourceInfo, "idn": "..."}}
        """
        candidates = self.find_serial_devices()
        logger.info(
            "find_ips_laser: %d serial candidate(s) detected", len(candidates)
        )

        connected_lasers: dict[str, dict] = {}

        for resource_name, resource_info in candidates.items():
            logger.info("find_ips_laser: probing %s", resource_name)
            try:
                dev = self.ressource_manage.open_resource(resource_name)

                # Apply serial configuration before probing
                try:
                    dev.baud_rate = baud_rate
                except Exception:
                    pass

                # Terminations matter a lot for SCPI-ish devices
                try:
                    dev.write_termination = "\n"
                    dev.read_termination = "\n"
                except Exception:
                    pass

                dev.timeout = timeout_ms

                idn = dev.query(idn_query).strip()
                logger.info(
                    "find_ips_laser: %s replied IDN=%r", resource_name, idn
                )

            except Exception as e:
                logger.warning(
                    "find_ips_laser: probe failed on %s (%s: %s)",
                    resource_name,
                    type(e).__name__,
                    e,
                )
                continue
            finally:
                # Don’t leave resources open after probing
                try:
                    dev.close()
                except Exception:
                    pass

            if match_substring in idn:
                connected_lasers[resource_name] = {
                    "ressourceInfo": resource_info,
                    "idn": idn,
                }
                logger.info(
                    "find_ips_laser: matched IPS device on %s", resource_name
                )

        logger.info(
            "find_ips_laser: %d IPS laser(s) found", len(connected_lasers)
        )
        return connected_lasers

    ## Basic methods

    def _safe_scpi_write(self, message: str) -> (int, str):
        """Sends a serial message to the laser and verifies if any communication error occured.

        Parameter : <message> (string) : Message send to the laser by serial.
        The command syntax for those messages is explained in the documentation provided by IPS.  %

        Returns:
        <err_code> : communication error code
        <err_message> : communication error message
        """
        if not self.isconnected:
            return 0, ERROR_CODES[0]
        with self._mutex:
            try:
                self.pyvisa_serial.write(message)
                err_msg = self.pyvisa_serial.query("Error?").strip()
                err_code = err_msg.split(",")[0]
                err_msg = err_msg.split(",")[-1].strip().strip('"')
            except Exception as e:
                logger.error(e)

        return err_code, err_msg

    def _safe_scpi_query(self, message: str) -> (str, int, str):
        """Sends a serial message to the laser, reads the err_code and
        verifies if any communication error occured.

        Parameter : <message> (string) : Message send to the laser by serial.
        The command syntax for those messages is explained in the documentation provided by IPS.  %

        Returns:
        <value> (string) : Answer provided by the laser to the serial COM.
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        with self._mutex:
            try:
                answer = self.pyvisa_serial.query(message).strip()
                err_msg = self.pyvisa_serial.query("Error?").strip()
                err_code = int(err_msg.split(",")[0])
                err_msg = err_msg.split(",")[-1].strip().strip('"')
            except Exception as e:
                logger.error(e)

        return answer, err_code, err_msg

    def __repr__(self) -> str:
        reprstr = (
            f"IPSLaser(idn = '{self.idn}', "
            f"comport = '{self.comport}', "
            f"connected = {self.isconnected}, "
            f"enabled = {self.isenabled}, "
            f"laser current = {self.info.laser_current} mA, "
            f" laser temperature = {self.info.laser_current}C, "
            f"laser power = {self.info.laser_power} mW)"
        )
        return reprstr

    ## Getters

    def get_id(self) -> tuple[str, int, str]:
        """Reports the device identification string. Will read back:
        IPS, HPU, laser serial number, factory measured wavelength, FW revision.

        Returns idn, err_code
        idn [str] : device identification string
        err_code [int] : hardware error code
        """
        idn, err_code, err_msg = self._safe_scpi_query("*IDN?")
        return idn, err_code, err_msg

    def get_status(self) -> tuple[int, int, str]:
        """Requests the status of the digital U-type.

        Response : 2 decimal numbers; the first number represents the board state:
        0 = unknown state
        1 = board passed POST
        2 = board failed POST
        3 = board in normal state
        4 = board in fault state
        5 = board in boot load state 6 = board not attached

        The second number is the number of errors in the hardware error queue.
        Use the “ERRor?” command to read the error code and information

        Returns: <status> : status of the digital U-type
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        answer, err_code, err_msg = self._safe_scpi_query("Status?")
        status_code = int(answer.split(",")[0])

        return status_code, err_code, err_msg

    def get_board_current(self) -> tuple[float, int, str]:
        """Reports the measured current draw in mA.

        Returns: <board_current> : measured current draw in mA
        <err_code> : communication error code
        <err_msg> : communication error message"""
        board_current, err_code, err_msg = self._safe_scpi_query(
            "Board:Current?"
        )
        board_current = str2float(board_current)
        return board_current, err_code, err_msg

    def get_board_temperature(self) -> tuple[float, int, str]:
        """Reports the module case temperature in °C.

        Returns: <board_temp> : module case temperature in °C
        <err_code> : communication error code
        <err_msg> : communication error message"""
        board_temp, err_code, err_msg = self._safe_scpi_query(
            "Board:Temperature?"
        )
        board_temp = str2float(board_temp)
        return board_temp, err_code, err_msg

    def get_calibrate_number(self) -> tuple[int, int, str]:
        """Reports number of entries in the LUT.

        Returns: <cal_num> : number of entries in the LUT
        <err_code> : communication error code
        <err_msg> : communication error message"""
        cal_num, err_code, err_msg = self._safe_scpi_query("Calibrate:Number?")
        cal_num = int(cal_num)
        return cal_num, err_code, err_msg

    def get_calibrate_monitor(self, num: int) -> tuple[float, int, str]:
        """Reports the PD monitor value in the requested <num> LUT entry in mV.

        Parameter: <num> (int) : the entry number in the LUT. Integers from 1 to 9

        Returns: <cal_mon> : PD monitor value in mV
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        cal_mon, err_code, err_msg = self._safe_scpi_query(
            "Calibrate:Monitor? " + str(num)
        )
        cal_mon = str2float(cal_mon)
        return cal_mon, err_code, err_msg

    def get_calibrate_power(self, num: int) -> tuple[float, int, str]:
        """Reports the laser power value in the requested <num> LUT entry in mW.

        Parameter: <num> (int) : the entry number in the LUT. Integers from 1 to 9

        Returns: <cal_pow> : laser power value in the LUT in mW
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        cal_pow, err_code, err_msg = self._safe_scpi_query(
            "Calibrate:Power? " + str(num)
        )
        cal_pow = str2float(cal_pow)
        return cal_pow, err_code, err_msg

    def get_laser_current(self) -> tuple[float, int, str]:
        """Reports measured laser operating current in mA.

        Returns: <laser_current> : measured laser operating current in mA
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        laser_current, err_code, err_msg = self._safe_scpi_query(
            "Laser:Current?"
        )
        laser_current = str2float(laser_current)
        return laser_current, err_code, err_msg

    def get_laser_setpoint(self) -> tuple[float, int, str]:
        """Reports the laser operating current setpoint in mA.

        Returns: <setpoint> : laser operating current setpoint in mA
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        setpoint, err_code, err_msg = self._safe_scpi_query("Laser:Setpoint?")
        setpoint = str2float(setpoint)
        return setpoint, err_code, err_msg

    def get_enable(self) -> tuple[bool, int, str]:
        """Reports laser enable state.

        Returns: <state> : laser enable state
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        state, err_code, err_msg = self._safe_scpi_query("Laser:Enable?")
        state = bool(int(state))
        return state, err_code, err_msg

    def get_laser_hours(self) -> tuple[float, int, str]:
        """Reports the number of hours of ON time of the laser.

        Returns: <hours> : number of hours of ON time of the laser
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        hours, err_code, err_msg = self._safe_scpi_query("Laser:Hours?")
        hours = str2float(hours)
        return hours, err_code, err_msg

    def get_analog_mode(self) -> tuple[int, int, str]:
        """Reports the external VBIAS enable state.

        A return of 0 = Factory Default setting (VBIAS is disabled)
        A return of 1 = External VBIAS is enabled

        Returns: <state> : external VBIAS enable state
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        analog_mode, err_code, err_msg = self._safe_scpi_query(
            "Laser:Mode:Analog?"
        )
        analog_mode = int(analog_mode)
        return analog_mode, err_code, err_msg

    def get_digital_mode(self, probed_mode: int = 0) -> tuple[int, int, str]:
        """Reports the external VBIAS enable state.

        Parameter :
        probed_mode (int) : None or 0 to report current laser mode digital (PWM) enable
        status, 1 to report laser mode digital (PWM) factory default setting

        Returns: <state> : external VBIAS enable state
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Mode:Digital? {probed_mode}"
        state, err_code, err_msg = self._safe_scpi_query(scpi_str)
        state = int(state)
        return state, err_code, err_msg

    def get_pwm_dutycycle(
        self, get_factory: bool = 0
    ) -> tuple[float, int, str]:
        """Reports the PWM duty cycle of laser current.

        Parameter : <default> (int) : None or 0 to report current laser PWM setting,
        1 to report factory default PWM setting

        Returns: <pmw> : PWM duty cycle of laser current
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Mode:PWM? {int(bool(get_factory))}"
        pwm, err_code, err_msg = self._safe_scpi_query(scpi_str)
        pwm = str2float(pwm)
        return pwm, err_code, err_msg

    def get_pd_level(self) -> [float, int, str]:
        """Reports the monitor photodiode (PD) signal level.

        Returns: <signal> : monitor photodiode (PD) signal level
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        signal, err_code, err_msg = self._safe_scpi_query("Laser:Monitor?")
        signal = str2float(signal)
        return signal, err_code, err_msg

    def get_laser_power(self) -> tuple[float, int, str]:
        """Reports the Laser Power in mW as derived from the calibration Look Up Table (LUT).

        Returns: <laser_power> : laser Power in mW as derived from the calibration Look Up Table
        (LUT)
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        laser_power, err_code, err_msg = self._safe_scpi_query("Laser:Power?")
        laser_power = str2float(laser_power)
        return laser_power, err_code, err_msg

    def get_laser_temperature(self) -> tuple[float, int, str]:
        """Reports the Laser/TEC Temperature in °C.

        Returns: <laser_temp> : Laser/TEC Temperature in °C
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        laser_temp, err_code, err_msg = self._safe_scpi_query(
            "Laser:Temperature?"
        )
        laser_temp = str2float(laser_temp)
        return laser_temp, err_code, err_msg

    def get_system_errors_count(self) -> tuple[float, int, str]:
        """Reports the number of errors in the communication error queue."""
        count, err_code, err_msg = self._safe_scpi_query("System:Error:Count?")
        count = int(count)
        return count, err_code, err_msg

    def get_tec_setpoint(
        self, factory_setting: bool = False
    ) -> tuple[float, int, str]:
        """Reports the setpoint target for the TEC temperature.

        Parameter : <default> (int) : None or 0: Report current laser TEC temperature setting,
        1: Report factory default TEC temperature setting

        Returns: <setpoint> : setpoint target for the TEC temperature
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str, err_code, err_msg = (
            f"TEC:SETpoint? {int(bool(factory_setting))}"
        )
        setpoint, err_code, err_msg = self._safe_scpi_query(scpi_str)
        setpoint = str2float(setpoint)
        return setpoint, err_code, err_msg

    # Setters

    def set_calibrate_number(
        self, num_entries: int, save_state: int = 0
    ) -> tuple[int, str]:
        """Sets number of desired entries in the calibration Look Up Table (LUT).

        Parameters :
        <num_entries> (int) : from 2 to 9
        <save_state> (int) : 1 = store permanently, and 0 = use until next power cycle
        If no value entered for <save state> default is to 0

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Calibrate:Number {num_entries} {save_state}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_calibrate_monitor(
        self, num: int, value: int, save_state: int = 0
    ) -> tuple[int, str]:
        """Sets photodiode (PD) monitor value in LUT in mV.

        Parameters:
        <num> (int) : the entry number in the LUT. Integers from 1 to 9
        <value> (int) : the value in the LUT. Integers from 0 to 3000
        <save_state> (int) : 1 = store permanently, and 0 = use until next power cycle
        If no value entered for <save state> default is to 0

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Calibrate:Monitor {num} {value} {save_state}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_calibrate_power(
        self, num: int, value: float, save_state: int = 0
    ) -> tuple[int, str]:
        """Sets LUT power value in mW.

        Parameters:
        <num> (int) : the entry number in the LUT. Integers from 1 to 9
        <value> (float) : <value> – the power value into the LUT. Floats from: 0 to 6553.5
        <save_state> (int) : 1 = store permanently, and 0 = use until next power cycle
        If no value entered for <save state> default is to 0

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Calibrate:Power {num} {value} {save_state}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_laser_current(self, current: float) -> tuple[int, str]:
        """Sets laser operating current setpoint in mA.

        Parameter : <current> is the laser operating current in mA

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        current = int(current)
        scpi_str = f"Laser:Current {current}"
        self.target_current = current
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_enable(self, enable: bool) -> tuple[int, str]:
        """Controls whether the laser is enabled or disabled.

        Parameter : <enable> (int) : 1/ON = Enables the Laser, 0/OFF = Disables the laser

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Enable {str(int(bool(enable)))}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        # Update reference
        if err_code == 0:
            self.isenabled = enable
        return err_code, err_msg

    def set_analog_mode(self, analog_on: bool) -> tuple[int, str]:
        """Enable/Disable VBIAS input from external hardware connection on pin 8 of module.
        This function allows the user to adjust the output power of the laser
        via an external voltage bias.

        Parameter : <enable> (int): 1/ON = Enables VBIAS input to control the laser current,
        0/OFF = Disables external VBIAS input;

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Mode:Analog {int(bool(analog_on))}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_digital_mode(self, digital_on: bool) -> tuple[int, str]:
        """Reports digital mode (PWM) enable status.

        Parameter : <enable> (int): 1 = Allows digital modulation of the laser current,
        0 = Do not allow digital modulation of the laser

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Mode:Digital {int(bool(digital_on))}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_pwm_dutycycle(self, dutycycle: float) -> tuple[int, str]:
        """Sets PWM percent (0 – 100) for digital mode.

        Parameter : <duty cycle> (float): PWM duty cycle in percent from 10.0% to 100%

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"Laser:Mode:PWM {dutycycle}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    def set_tec_setpoint(self, temperature: float) -> tuple[int, str]:
        """Sets the setpoint target for the TEC temperature.

        Parameters : <temperature> (float) : The set point temperature in oC degrees for the
        laserTEC.

        Acceptable values range from 10.0 to 45.0. Optimal setting is between 30°C - 35°C
        for most system configurations.

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        scpi_str = f"TEC:SETpoint {temperature}"
        err_code, err_msg = self._safe_scpi_write(scpi_str)
        return err_code, err_msg

    # Advanced methods (USE WITH CARE)

    def restore_factory_settings(self) -> tuple[int, str]:
        """Restores the default power-up configuration to the IPS factory default.
        To save the default parameters, you must add a "Parameters:Save command"
        following the "Parameters:Restore" command.

        The parameters restored are: TEC_Setpoint, Laser_Drive, Laser Enable Mode,
        Analog Mode Enable, Digital Mode Enable, and PWM Duty Cycle.

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        err_code, err_msg = self._safe_scpi_write("Parameters:Restore")
        return err_code, err_msg

    def overwrite_factory_settings(self) -> tuple[int, str]:
        """Saves current parameter settings to FLASH for use as default power-up configuration
        (Note: At present, there is no IPS factory “as shipped” setting,
        so it is recommended that users document parameters before changing them
        so that they can be returned to the IPS default set state if desired).

        The parameters stored to FLASH are: TEC_Setpoint, Laser_Drive, Laser Enable Mode,
        Analog Mode Enable, Digital Mode Enable and PWM Duty Cycle.

        Returns:
        <err_code> : communication error code
        <err_msg> : communication error message
        """
        err_code, err_msg = self._safe_scpi_write("Parameters:Save")
        return err_code, err_msg

    # Compound methods

    def connect(self) -> bool:
        """Connects the laser"""
        try:
            self.pyvisa_serial = self.ressource_manage.open_resource(
                self.comport
            )
            self.isconnected = True
        except Exception as _:
            self.isconnected = False

        return self.isconnected

    def disconnect(self) -> str:
        """Close the serial connection to the laser,
        disable laser if enabled."""
        self.set_laser_current(0)
        self.set_enable(0)
        self.isconnected = False
        self.idn = None
        self.pyvisa_serial.close()
        return not self.isconnected

    def get_info(self) -> None:
        if not self.isconnected:
            self.info = IPSInfo()

        try:
            _, model, serial_number, wavelength, _ = self.get_id()[0].split(
                ","
            )
            is_enabled = self.get_enable()[0]
            temperature = self.get_laser_temperature()[0]
            current = self.get_laser_current()[0]
            power = self.get_laser_power()[0]
            self.info = IPSInfo(
                is_connected=True,
                is_enabled=is_enabled,
                model=model.strip(),
                serial_number=serial_number.strip(),
                wavelength=float(wavelength),
                temperature=temperature,
                laser_current=current,
                laser_power=power,
                laser_target_current=self.target_current,
            )
        except Exception as _:
            self.info = IPSInfo()


if __name__ == "__main__":

    ips = IpsLaser()

    print("... Looking for connected lasers ...\n")
    available_lasers = ips.find_ips_laser()

    print("Connected lasers:")
    if available_lasers:
        for i, laser in enumerate(available_lasers):
            print(f"\t{i}) ", laser)
        selected_laser = int(
            input(
                "\nSelect a laser (default : 0) :",
            )
            or 0
        )
        ips.comport = list(ips.find_ips_laser())[selected_laser]
    else:
        print("\tNo laser found")
        exit()

    print(f"Connecting to laser {ips.comport}")
    ips.connect()

    ips.get_info()
    print(ips.info)

    print(ips.get_laser_power())
    print(ips.get_laser_temperature())

    ips.disconnect()
