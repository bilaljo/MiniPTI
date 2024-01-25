import functools
import typing
from abc import ABC
from dataclasses import dataclass

from PyQt5 import QtWidgets, QtCore

from minipti.gui import model
from minipti.gui.controller import interface
from minipti.gui.view import helper


class Slider(QtWidgets.QWidget):
    def __init__(self, minimum=0, maximum=100, unit="%"):
        QtWidgets.QWidget.__init__(self)
        self.slider = QtWidgets.QSlider()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.slider)
        self.slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.slider_value = QtWidgets.QLabel()
        self.layout().addWidget(self.slider_value)
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.unit = unit
        self.index_value = 0

    @functools.singledispatchmethod
    def update_value(self, value: int) -> None:
        self.slider_value.setText(f"{value} " + self.unit)

    @update_value.register
    def _(self, value: float) -> None:
        self.slider_value.setText(f"{round(value, 2)} " + self.unit)


@dataclass
class DriverButtons:
    save: QtWidgets.QPushButton
    save_as: QtWidgets.QPushButton
    load: QtWidgets.QPushButton
    apply: QtWidgets.QPushButton


@dataclass
class Frames(ABC):
    ...


class DriverConfig(QtWidgets.QWidget):
    def __init__(self, controller: interface.Driver):
        QtWidgets.QWidget.__init__(self)
        self.controller = controller
        self.configuration_buttons = DriverButtons(save_as=QtWidgets.QPushButton(),
                                                   save=QtWidgets.QPushButton(), load=QtWidgets.QPushButton(),
                                                   apply=QtWidgets.QPushButton())
        self.setLayout(QtWidgets.QVBoxLayout())
        self._init_buttons()

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.configuration_buttons.save = helper.create_button(parent=sub_layout, title="Save",
                                                               slot=self.controller.save_configuration)
        self.configuration_buttons.save_as = helper.create_button(parent=sub_layout, title="Save As",
                                                                  slot=self.controller.save_configuration_as)
        self.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.configuration_buttons.load = helper.create_button(parent=sub_layout, title="Load",
                                                               slot=self.controller.load_configuration)
        self.configuration_buttons.apply = helper.create_button(parent=sub_layout, title="Apply Configuration",
                                                                slot=self.controller.apply_configuration)
        self.layout().addWidget(sub_layout)


@dataclass
class PumpLaserFrames:
    measured_values: QtWidgets.QGroupBox
    driver_voltage: QtWidgets.QGroupBox
    current: list[QtWidgets.QGroupBox]
    configuration: QtWidgets.QGroupBox
    enable: QtWidgets.QGroupBox


class PumpLaser(QtWidgets.QWidget):
    _MIN_DRIVER_BIT = 0
    _MAX_DRIVER_BIT = (1 << 7) - 1
    _MIN_CURRENT = 0
    _MAX_CURRENT = (1 << 12) - 1

    def __init__(self, controller: interface.PumpLaser):
        QtWidgets.QWidget.__init__(self)
        self.frames = PumpLaserFrames(QtWidgets.QGroupBox(), QtWidgets.QGroupBox(),
                                      [QtWidgets.QGroupBox(), QtWidgets.QGroupBox()], QtWidgets.QGroupBox(),
                                      QtWidgets.QGroupBox())
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller
        self.driver_config = DriverConfig(controller)
        self.current_display = QtWidgets.QLabel("0 mA")
        self.voltage_display = QtWidgets.QLabel("0 V")
        self.driver_voltage = Slider(minimum=PumpLaser._MIN_DRIVER_BIT, maximum=PumpLaser._MAX_DRIVER_BIT, unit="V")
        self.current = [Slider(minimum=PumpLaser._MIN_CURRENT, maximum=PumpLaser._MAX_CURRENT, unit="Bit"),
                        Slider(minimum=PumpLaser._MIN_CURRENT, maximum=PumpLaser._MAX_CURRENT, unit="Bit")]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self.enable_button: QtWidgets.QPushButton | None = None
        self._init_frames()
        self._init_buttons()
        self.frames.driver_voltage.layout().addWidget(self.driver_voltage)
        self._init_measured_value()
        self._init_current_configuration()
        self._init_voltage_configuration()
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_measured_value(self) -> None:
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.current_display)
        sublayout.layout().addWidget(self.voltage_display)
        self.frames.measured_values.layout().addWidget(sublayout)

    def _init_signals(self) -> None:
        model.signals.LASER.laser_voltage.connect(self._update_voltage_slider)
        model.signals.LASER.current_dac.connect(self._update_current_dac)
        model.signals.LASER.matrix_dac.connect(self._update_dac_matrix)
        model.signals.LASER.data_display.connect(self._update_current_voltage)
        model.signals.LASER.pump_laser_enabled.connect(self.enable)

    @QtCore.pyqtSlot(model.serial_devices.LaserData)
    def _update_current_voltage(self, value: model.serial_devices.LaserData) -> None:
        self.current_display.setText(str(value.high_power_laser_current) + " mA")
        self.voltage_display.setText(str(value.high_power_laser_voltage) + " V")

    @QtCore.pyqtSlot(bool)
    def enable(self, state: bool):
        helper.toggle_button(state, self.enable_button)

    def _init_voltage_configuration(self) -> None:
        self.driver_voltage.slider.valueChanged.connect(self.controller.update_driver_voltage)

    def _init_current_configuration(self) -> None:
        self.current[0].slider.valueChanged.connect(self.controller.update_current_dac1)
        self.current[1].slider.valueChanged.connect(self.controller.update_current_dac2)
        for i in range(3):
            self.mode_matrix[0][i].currentIndexChanged.connect(self.controller.update_dac1(i))
            self.mode_matrix[1][i].currentIndexChanged.connect(self.controller.update_dac2(i))

    @QtCore.pyqtSlot(int, list)
    def _update_dac_matrix(self, dac_number: int, configuration: typing.Annotated[list[int], 3]) -> None:
        for channel in range(3):
            self.mode_matrix[dac_number][channel].setCurrentIndex(configuration[channel])

    @QtCore.pyqtSlot(int, float)
    def _update_voltage_slider(self, index: int, value: float) -> None:
        self.driver_voltage.slider.setValue(index)
        self.driver_voltage.update_value(value)

    @QtCore.pyqtSlot(int, int)
    def _update_current_dac(self, dac: int, index: int) -> None:
        self.current[dac].slider.setValue(index)
        self.current[dac].update_value(index)

    def _init_frames(self) -> None:
        self.frames.measured_values = helper.create_frame(parent=self, title="Measured Values", x_position=0,
                                                          y_position=0)
        self.frames.driver_voltage = helper.create_frame(parent=self, title="Driver Voltage", x_position=1,
                                                         y_position=0)
        for i in range(2):
            self.frames.current[i] = helper.create_frame(parent=self, title=f"DAC {i + 1}", x_position=i + 2,
                                                         y_position=0)
        self.frames.configuration = helper.create_frame(parent=self, title="Configuration", x_position=5, y_position=0)

    def _init_buttons(self) -> None:
        dac_inner_frames = [QtWidgets.QWidget() for _ in range(2)]  # For slider and button-matrices
        for j in range(2):
            dac_inner_frames[j].setLayout(QtWidgets.QGridLayout())
            self.frames.current[j].layout().addWidget(self.current[j])
            for i in range(3):
                sub_frames = [QtWidgets.QWidget() for _ in range(3)]
                sub_frames[i].setLayout(QtWidgets.QVBoxLayout())
                dac_inner_frames[j].layout().addWidget(sub_frames[i], 1, i)
                self.mode_matrix[j][i].addItem("Disabled")
                self.mode_matrix[j][i].addItem("Continuous Wave")
                self.mode_matrix[j][i].addItem("Pulsed Mode")
                sub_frames[i].layout().addWidget(QtWidgets.QLabel(f"Channel {i + 1}"))
                sub_frames[i].layout().addWidget(self.mode_matrix[j][i])
            self.frames.current[j].layout().addWidget(dac_inner_frames[j])
        self.frames.configuration.layout().addWidget(self.driver_config, 4, 0)
        self.enable_button = helper.create_button(self, title="Enable", slot=self.controller.enable)


@dataclass
class ProbeLaserFrames:
    maximum_current: QtWidgets.QGroupBox
    measured_values: QtWidgets.QGroupBox
    current: QtWidgets.QGroupBox
    mode: QtWidgets.QGroupBox
    photo_diode_gain: QtWidgets.QGroupBox
    configuration: QtWidgets.QGroupBox


class ProbeLaser(QtWidgets.QWidget):
    MIN_CURRENT_BIT = 10  # Heuristic value. Is needed to be > 0 to avoid current peaks at start up
    MAX_CURRENT_BIT = (1 << 8) - 1
    CONSTANT_CURRENT = 0
    CONSTANT_LIGHT = 1

    def __init__(self, controller: interface.ProbeLaser):
        QtWidgets.QWidget.__init__(self)
        self.controller = controller
        self.setLayout(QtWidgets.QGridLayout())
        self.driver_config = DriverConfig(controller)
        self.current_slider = Slider(minimum=ProbeLaser.MIN_CURRENT_BIT, maximum=ProbeLaser.MAX_CURRENT_BIT, unit="mA")
        self.frames = ProbeLaserFrames(QtWidgets.QGroupBox(), QtWidgets.QGroupBox(), QtWidgets.QGroupBox(),
                                       QtWidgets.QGroupBox(), QtWidgets.QGroupBox(), QtWidgets.QGroupBox())
        self.laser_mode = QtWidgets.QComboBox()
        self.photo_gain = QtWidgets.QComboBox()
        self.current_display = QtWidgets.QLabel("0 mA")
        self.enable_button: QtWidgets.QPushButton | None = None
        self._init_frames()
        self._init_slider()
        self._init_buttons()
        self.frames.measured_values.layout().addWidget(self.current_display)
        self.max_current_display = QtWidgets.QLineEdit("")
        self.frames.maximum_current.layout().addWidget(self.max_current_display, 0, 0)
        self.frames.maximum_current.layout().addWidget(QtWidgets.QLabel("mA"), 0, 1)
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        self.photo_gain.currentIndexChanged.connect(self.controller.update_photo_gain)
        self.laser_mode.currentIndexChanged.connect(self.controller.update_probe_laser_mode)
        self.max_current_display.editingFinished.connect(self._max_current_changed)
        model.signals.LASER.current_probe_laser.connect(self._update_current_slider)
        model.signals.LASER.photo_gain.connect(self._update_photo_gain)
        model.signals.LASER.probe_laser_mode.connect(self._update_mode)
        model.signals.LASER.data_display.connect(self._update_current)
        model.signals.LASER.max_current_probe_laser.connect(self._update_max_current)
        model.signals.LASER.probe_laser_enabled.connect(self.enable)

    @QtCore.pyqtSlot(model.serial_devices.LaserData)
    def _update_current(self, value: model.serial_devices.LaserData) -> None:
        self.current_display.setText(str(value.low_power_laser_current) + " mA")

    @QtCore.pyqtSlot(bool)
    def enable(self, state: bool):
        helper.toggle_button(state, self.enable_button)

    @functools.singledispatchmethod
    def _update_max_current(self, value: int):
        self.max_current_display.setText(str(value))

    @_update_max_current.register
    def _(self, value: float):
        self.max_current_display.setText(str(round(value, 2)))

    def _max_current_changed(self) -> None:
        return self.controller.update_max_current_probe_laser(self.max_current_display.text())

    def _init_frames(self) -> None:
        self.frames.maximum_current = helper.create_frame(parent=self, title="Maximum Current", x_position=0,
                                                          y_position=0)
        self.frames.measured_values = helper.create_frame(parent=self, title="Measured Values", x_position=1,
                                                          y_position=0)
        self.frames.current = helper.create_frame(parent=self, title="Current", x_position=2, y_position=0)
        self.frames.mode = helper.create_frame(parent=self, title="Mode", x_position=3, y_position=0)
        self.frames.photo_diode_gain = helper.create_frame(parent=self, title="Photo Diode Gain", x_position=4,
                                                           y_position=0)
        self.frames.configuration = helper.create_frame(parent=self, title="Configuration", x_position=5, y_position=0)

    def _init_slider(self) -> None:
        self.frames.current.layout().addWidget(self.current_slider)
        self.current_slider.slider.valueChanged.connect(self.controller.update_current_probe_laser)

    @QtCore.pyqtSlot(int, float)
    def _update_current_slider(self, index: int, value: float) -> None:
        self.current_slider.slider.setValue(index)
        self.current_slider.update_value(value)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.laser_mode.addItem("Constant Light")
        self.laser_mode.addItem("Constant Current")
        sub_layout.layout().addWidget(self.laser_mode)
        self.frames.mode.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.photo_gain.addItem("1x")
        self.photo_gain.addItem("2x")
        self.photo_gain.addItem("3x")
        self.photo_gain.addItem("4x")
        sub_layout.layout().addWidget(self.photo_gain)
        self.frames.photo_diode_gain.layout().addWidget(sub_layout)
        self.frames.configuration.layout().addWidget(self.driver_config, 3, 0)
        self.enable_button = helper.create_button(self, title="Enable", slot=self.controller.enable)

    @QtCore.pyqtSlot(int)
    def _update_photo_gain(self, index: int) -> None:
        self.photo_gain.setCurrentIndex(index)

    @QtCore.pyqtSlot(int)
    def _update_mode(self, index: int):
        self.laser_mode.setCurrentIndex(index)


@dataclass
class TecTextFields:
    p_gain: QtWidgets.QLineEdit
    i_gain: QtWidgets.QLineEdit
    d_gain: QtWidgets.QLineEdit
    setpoint_temperature: QtWidgets.QLineEdit
    loop_time: QtWidgets.QLineEdit
    max_power: QtWidgets.QLineEdit


@dataclass
class TecFrames:
    temperature: QtWidgets.QGroupBox
    pid_configuration: QtWidgets.QGroupBox
    system_settings: QtWidgets.QGroupBox
    configuration: QtWidgets.QGroupBox


class Tec(QtWidgets.QWidget):
    def __init__(self, controller: interface.Tec, laser: int):
        QtWidgets.QWidget.__init__(self)
        self.controller = controller
        self.driver_config = DriverConfig(controller)
        self.frames = TecFrames(QtWidgets.QGroupBox(), QtWidgets.QGroupBox(), QtWidgets.QGroupBox(),
                                QtWidgets.QGroupBox())
        self.laser = laser
        self.setLayout(QtWidgets.QGridLayout())
        self.text_fields = TecTextFields(QtWidgets.QLineEdit(), QtWidgets.QLineEdit(), QtWidgets.QLineEdit(),
                                         QtWidgets.QLineEdit(), QtWidgets.QLineEdit(), QtWidgets.QLineEdit())
        self.temperature_display = QtWidgets.QLabel("NaN °C")
        self.enable_button: QtWidgets.QPushButton | None = None
        self._init_frames()
        self._init_text_fields()
        self._init_signals()
        self._init_buttons()
        self.frames.temperature.layout().addWidget(self.temperature_display)
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.signals.GENERAL_PURPORSE.tec_data_display.connect(self.update_temperature)
        model.signals.TEC[self.laser].p_gain.connect(Tec._update_text_field(self.text_fields.p_gain))
        model.signals.TEC[self.laser].i_gain.connect(Tec._update_text_field(self.text_fields.i_gain))
        model.signals.TEC[self.laser].d_gain.connect(Tec._update_text_field(self.text_fields.d_gain))
        model.signals.TEC[self.laser].setpoint_temperature.connect(
            Tec._update_text_field(self.text_fields.setpoint_temperature))
        model.signals.TEC[self.laser].loop_time.connect(Tec._update_text_field(self.text_fields.loop_time,
                                                                               floating=False))
        model.signals.TEC[self.laser].max_power.connect(Tec._update_text_field(self.text_fields.max_power,
                                                                               floating=True))
        model.signals.TEC[self.laser].enabled.connect(self.update_enable)

    def _init_frames(self) -> None:
        self.frames.temperature = helper.create_frame(parent=self, title="Temperature", x_position=0, y_position=0)
        self.frames.pid_configuration = helper.create_frame(parent=self, title="PID Configuration", x_position=1,
                                                            y_position=0, x_span=2)
        self.frames.system_settings = helper.create_frame(parent=self, title="System Settings", x_position=3,
                                                          y_position=0, x_span=2)
        self.frames.configuration = helper.create_frame(parent=self, title="Configuration", x_position=5, y_position=0,
                                                        x_span=2)

    def _init_buttons(self) -> None:
        self.frames.configuration.layout().addWidget(self.driver_config, 3, 0)
        self.enable_button = helper.create_button(self, title="Enable", slot=self.controller.enable)

    @QtCore.pyqtSlot(bool)
    def update_enable(self, state: bool):
        helper.toggle_button(state, self.enable_button)

    @staticmethod
    def _update_text_field(text_field: QtWidgets.QLineEdit, floating=True):
        if floating:
            @QtCore.pyqtSlot(float)
            def update(value: float) -> None:
                text_field.setText(str(round(value, 2)))
        else:
            @QtCore.pyqtSlot(int)
            def update(value: int) -> None:
                text_field.setText(str(value))
        return update

    @QtCore.pyqtSlot(model.serial_devices.TecData)
    def update_temperature(self, value: model.serial_devices.TecData) -> None:
        self.temperature_display.setText(f"{round(value.actual_temperature[self.laser], 3)} °C")

    def _init_text_fields(self) -> None:
        self.frames.pid_configuration.layout().addWidget(QtWidgets.QLabel("P Gain [°C⁻¹]"), 0, 0)
        self.frames.pid_configuration.layout().addWidget(self.text_fields.p_gain, 0, 1)
        self.text_fields.p_gain.editingFinished.connect(self.p_gain_changed)

        self.frames.pid_configuration.layout().addWidget(QtWidgets.QLabel("I Gain [°C⁻¹]"), 2, 0)
        self.frames.pid_configuration.layout().addWidget(self.text_fields.i_gain, 2, 1)
        self.text_fields.i_gain.editingFinished.connect(self.i_gain_changed)

        self.frames.pid_configuration.layout().addWidget(QtWidgets.QLabel("D Gain [°C⁻¹]"), 6, 0)
        self.frames.pid_configuration.layout().addWidget(self.text_fields.d_gain, 6, 1)
        self.text_fields.d_gain.editingFinished.connect(self.d_gain_changed)

        self.frames.system_settings.layout().addWidget(QtWidgets.QLabel("Setpoint Temperature [°C]"), 0, 0)
        self.frames.system_settings.layout().addWidget(self.text_fields.setpoint_temperature, 0, 1)
        self.text_fields.setpoint_temperature.editingFinished.connect(self.setpoint_temperature_changed)

        self.frames.system_settings.layout().addWidget(QtWidgets.QLabel("Loop Time [ms]"), 1, 0)
        self.frames.system_settings.layout().addWidget(self.text_fields.loop_time, 1, 1)
        self.text_fields.loop_time.editingFinished.connect(self.loop_time_changed)

        self.frames.system_settings.layout().addWidget(QtWidgets.QLabel("Max Power [%]"), 3, 0)
        self.frames.system_settings.layout().addWidget(self.text_fields.max_power, 3, 1)
        self.text_fields.max_power.editingFinished.connect(self.max_power_changed)

        self.frames.system_settings.layout().addWidget(self.temperature_display)

    def d_gain_changed(self) -> None:
        self.controller.update_d_gain(self.text_fields.d_gain.text())

    def i_gain_changed(self) -> None:
        self.controller.update_i_gain(self.text_fields.i_gain.text())

    def p_gain_changed(self) -> None:
        self.controller.update_p_gain(self.text_fields.p_gain.text())

    def setpoint_temperature_changed(self) -> None:
        self.controller.update_setpoint_temperature(self.text_fields.setpoint_temperature.text())

    def loop_time_changed(self) -> None:
        self.controller.update_loop_time(self.text_fields.loop_time.text())

    def max_power_changed(self) -> None:
        self.controller.update_max_power(self.text_fields.max_power.text())
