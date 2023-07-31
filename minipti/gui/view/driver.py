import functools
import enum

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from .. import controller
from .. import model


class _CreateConfigurationButtons(_CreateButton):
    def __init__(self, parent_controller):
        _CreateButton.__init__(self)
        self.controller = parent_controller

    def __call__(self) -> QtWidgets.QWidget:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QVBoxLayout())
        self.create_button(master=sub_layout, title="Save Configuration",
                           slot=self.controller.save_configuration)
        self.create_button(master=sub_layout, title="Save Configuration As",
                           slot=self.controller.save_configuration_as)
        config.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Load Configuration",
                           slot=self.controller.load_configuration)
        self.create_button(master=sub_layout, title="Apply Configuration",
                           slot=self.controller.apply_configuration)
        config.layout().addWidget(sub_layout)
        return config


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


class PumpLaserFrames(Frames):
    measured_values = QtWidgets.QGroupBox()
    driver_voltage = QtWidgets.QGroupBox()
    current = [QtWidgets.QGroupBox(), QtWidgets.QGroupBox()]
    configuration = QtWidgets.QGroupBox()
    enable = QtWidgets.QGroupBox()


class PumpLaser(QtWidgets.QWidget, _CreateButton):
    class ModeIndices(enum.IntEnum):
        DISABLED = 0
        CONTINUOUS_WAVE = 1
        PULSED = 2

    _MIN_DRIVER_BIT = 0
    _MAX_DRIVER_BIT = (1 << 7) - 1
    _MIN_CURRENT = 0
    _MAX_CURRENT = (1 << 12) - 1

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        _CreateButton.__init__(self)
        self.model = None
        self.setLayout(QtWidgets.QGridLayout())
        self.current_display = QtWidgets.QLabel("0 mA")
        self.voltage_display = QtWidgets.QLabel("0 V")
        self.frames = PumpLaserFrames()
        self.driver_voltage = Slider(minimum=PumpLaser._MIN_DRIVER_BIT, maximum=PumpLaser._MAX_DRIVER_BIT, unit="V")
        self.current = [Slider(minimum=PumpLaser._MIN_CURRENT, maximum=PumpLaser._MAX_CURRENT, unit="Bit"),
                        Slider(minimum=PumpLaser._MIN_CURRENT, maximum=PumpLaser._MAX_CURRENT, unit="Bit")]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self.controller = controller.PumpLaser(self)
        self.create_configuration_buttons = _CreateConfigurationButtons(self.controller)
        self._init_frames()
        self._init_current_configuration()
        self._init_voltage_configuration()
        self._init_buttons()
        self.frames["Driver Voltage"].layout().addWidget(self.driver_voltage)
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.current_display)
        sublayout.layout().addWidget(self.voltage_display)
        self.frames["Measured Values"].layout().addWidget(sublayout)
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.laser_signals.laser_voltage.connect(self._update_voltage_slider)
        model.laser_signals.current_dac.connect(self._update_current_dac)
        model.laser_signals.matrix_dac.connect(self._update_dac_matrix)
        model.laser_signals.data_display.connect(self._update_current_voltage)
        model.laser_signals.pump_laser_enabled.connect(self.enable)

    @QtCore.pyqtSlot(hardware.laser.Data)
    def _update_current_voltage(self, value: hardware.laser.Data) -> None:
        self.current_display.setText(str(value.high_power_laser_current) + " mA")
        self.voltage_display.setText(str(value.high_power_laser_voltage) + " V")

    @QtCore.pyqtSlot(bool)
    def enable(self, state: bool):
        toggle_button(state, self.buttons["Enable"])

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
            if configuration[channel] == model.Mode.CONTINUOUS_WAVE:
                self.mode_matrix[dac_number][channel].setCurrentIndex(PumpLaser.ModeIndices.CONTINUOUS_WAVE)
            elif configuration[channel] == model.Mode.PULSED:
                self.mode_matrix[dac_number][channel].setCurrentIndex(PumpLaser.ModeIndices.PULSED)
            elif configuration[channel] == model.Mode.DISABLED:
                self.mode_matrix[dac_number][channel].setCurrentIndex(PumpLaser.ModeIndices.DISABLED)

    @QtCore.pyqtSlot(int, float)
    def _update_voltage_slider(self, index: int, value: float) -> None:
        self.driver_voltage.slider.setValue(index)
        self.driver_voltage.update_value(value)

    @QtCore.pyqtSlot(int, int)
    def _update_current_dac(self, dac: int, index: int) -> None:
        self.current[dac].slider.setValue(index)
        self.current[dac].update_value(index)

    def _init_frames(self) -> None:
        self.frames.set_frame(master=self, title="Measured Values", x_position=1, y_position=0)
        self.frames.set_frame(master=self, title="Driver Voltage", x_position=2, y_position=0)
        for i in range(1, 3):
            self.frames.set_frame(master=self, title=f"Current {i}", x_position=i + 2, y_position=0)
        self.frames.set_frame(master=self, title="Configuration", x_position=5, y_position=0)
        self.create_button(master=self, title="Enable", slot=self.controller.enable_pump_laser,  master_title="")

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
        config = self.create_configuration_buttons()
        self.frames.configuration.layout().addWidget(config, 3, 0)
        self.frames.configuration.layout().addWidget(config, 4, 0)


class ProbeLaser(QtWidgets.QWidget, _CreateButton):
    MIN_CURRENT_BIT = 5
    MAX_CURRENT_BIT = (1 << 8) - 1
    CONSTANT_CURRENT = 0
    CONSTANT_LIGHT = 1

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        _CreateButton.__init__(self)
        self.frames = {}
        self.setLayout(QtWidgets.QGridLayout())
        self.current_slider = Slider(minimum=ProbeLaser.MIN_CURRENT_BIT, maximum=ProbeLaser.MAX_CURRENT_BIT, unit="mA")
        self.controller = controller.ProbeLaser(self)
        self.laser_mode = QtWidgets.QComboBox()
        self.photo_gain = QtWidgets.QComboBox()
        self.current_display = QtWidgets.QLabel("0")
        self.create_configuration_buttons = _CreateConfigurationButtons(self.controller)
        self._init_frames()
        self._init_slider()
        self._init_buttons()
        self.photo_gain.currentIndexChanged.connect(self.controller.update_photo_gain)
        self.laser_mode.currentIndexChanged.connect(self.controller.update_probe_laser_mode)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.max_current_display = QtWidgets.QLineEdit("")
        self.max_current_display.editingFinished.connect(self._max_current_changed)
        self.frames["Maximum Current"].layout().addWidget(self.max_current_display, 0, 0)
        self.frames["Maximum Current"].layout().addWidget(QtWidgets.QLabel("mA"), 0, 1)
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.laser_signals.current_probe_laser.connect(self._update_current_slider)
        model.laser_signals.photo_gain.connect(self._update_photo_gain)
        model.laser_signals.probe_laser_mode.connect(self._update_mode)
        model.laser_signals.data_display.connect(self._update_current)
        model.laser_signals.max_current_probe_laser.connect(self._update_max_current)
        model.laser_signals.probe_laser_enabled.connect(self.enable)

    @QtCore.pyqtSlot(hardware.laser.Data)
    def _update_current(self, value: hardware.laser.Data) -> None:
        self.current_display.setText(str(value.low_power_laser_current))

    @QtCore.pyqtSlot(bool)
    def enable(self, state: bool):
        toggle_button(state, self.buttons["Enable"])

    @functools.singledispatchmethod
    def _update_max_current(self, value: int):
        self.max_current_display.setText(str(value))

    @_update_max_current.register
    def _(self, value: float):
        self.max_current_display.setText(str(round(value, 2)))

    def _max_current_changed(self) -> None:
        return self.controller.update_max_current_probe_laser(self.max_current_display.text())

    def _init_frames(self) -> None:
        self.create_frame(master=self, title="Maximum Current", x_position=0, y_position=0)
        self.create_frame(master=self, title="Measured Values", x_position=1, y_position=0)
        self.create_frame(master=self, title="Current", x_position=2, y_position=0)
        self.create_frame(master=self, title="Mode", x_position=3, y_position=0)
        self.create_frame(master=self, title="Photo Diode Gain", x_position=4, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=5, y_position=0)

    def _init_slider(self) -> None:
        self.frames["Current"].layout().addWidget(self.current_slider)
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
        self.frames["Mode"].layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.photo_gain.addItem("1x")
        self.photo_gain.addItem("2x")
        self.photo_gain.addItem("3x")
        self.photo_gain.addItem("4x")
        sub_layout.layout().addWidget(self.photo_gain)
        self.frames["Photo Diode Gain"].layout().addWidget(sub_layout)
        config = self.create_configuration_buttons()
        self.frames["Configuration"].layout().addWidget(config, 3, 0)
        self.create_button(self, title="Enable", slot=self.controller.enable_laser, master_title="")

    @QtCore.pyqtSlot(int)
    def _update_photo_gain(self, index: int) -> None:
        self.photo_gain.setCurrentIndex(index)

    @QtCore.pyqtSlot(int)
    def _update_mode(self, index: int):
        self.laser_mode.setCurrentIndex(index)


class TecTextFields:
    def __init__(self):
        self.p_value = QtWidgets.QLineEdit()
        self.i_value = [QtWidgets.QLineEdit(), QtWidgets.QLineEdit()]
        self.d_value = QtWidgets.QLineEdit()
        self.setpoint_temperature = QtWidgets.QLineEdit()
        self.loop_time = QtWidgets.QLineEdit()
        self.reference_resistor = QtWidgets.QLineEdit()
        self.max_power = QtWidgets.QLineEdit()


class Tec(QtWidgets.QWidget, _Frames, _CreateButton):
    def __init__(self, laser: int):
        QtWidgets.QWidget.__init__(self)
        _Frames.__init__(self)
        _CreateButton.__init__(self)
        self.laser = laser
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Tec(laser, self)
        self.text_fields = TecTextFields()
        self.temperature_display = QtWidgets.QLabel("NaN °C")
        self.create_configuration_buttons = _CreateConfigurationButtons(self.controller)
        self._init_frames()
        self._init_text_fields()
        self._init_buttons()
        self._init_signals()
        self.controller.fire_configuration_change()
        model.tec_signals[self.laser].enabled.connect(self.update_enable)

    def _init_signals(self) -> None:
        model.signals.tec_data_display.connect(self.update_temperature)
        model.tec_signals[self.laser].p_value.connect(Tec._update_text_field(self.text_fields.p_value))
        model.tec_signals[self.laser].i_1_value.connect(Tec._update_text_field(self.text_fields.i_value[0]))
        model.tec_signals[self.laser].i_2_value.connect(Tec._update_text_field(self.text_fields.i_value[1]))
        model.tec_signals[self.laser].d_value.connect(Tec._update_text_field(self.text_fields.d_value))
        model.tec_signals[self.laser].setpoint_temperature.connect(
            Tec._update_text_field(self.text_fields.setpoint_temperature))
        model.tec_signals[self.laser].loop_time.connect(Tec._update_text_field(self.text_fields.loop_time,
                                                                               floating=False))
        model.tec_signals[self.laser].reference_resistor.connect(
            Tec._update_text_field(self.text_fields.reference_resistor))
        model.tec_signals[self.laser].max_power.connect(Tec._update_text_field(self.text_fields.max_power,
                                                                               floating=False))
        model.tec_signals[self.laser].mode.connect(self.update_mode)

    def _init_frames(self) -> None:
        self.create_frame(master=self, title="PID Configuration", x_position=0, y_position=0)
        self.create_frame(master=self, title="System Settings", x_position=1, y_position=0)
        self.create_frame(master=self, title="Temperature", x_position=2, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=3, y_position=0)

    @QtCore.pyqtSlot(bool)
    def update_enable(self, state: bool):
        toggle_button(state, self.buttons["Enable"])

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

    @QtCore.pyqtSlot(hardware.tec.Data)
    def update_temperature(self, value: hardware.tec.Data) -> None:
        self.temperature_display.setText(str(value.actual_temperature[self.laser]) + " °C")

    @QtCore.pyqtSlot(model.TecMode)
    def update_mode(self, mode: model.TecMode):
        if mode == model.TecMode.COOLING:
            toggle_button(False, self.buttons["Heat"])
            toggle_button(True, self.buttons["Cool"])
        else:
            toggle_button(True, self.buttons["Heat"])
            toggle_button(False, self.buttons["Cool"])

    @QtCore.pyqtSlot(bool)
    def _update_resistor_visibility(self, use_ntc: bool) -> None:
        self.text_fields.reference_resistor.setDisabled(use_ntc)

    def _init_text_fields(self) -> None:
        self.create_button(master=self, title="Enable", slot=self.controller.enable,
                           master_title="")
        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("P Value"), 0, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.p_value, 0, 1)
        self.text_fields.p_value.editingFinished.connect(self.p_value_changed)

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>1</sub> Value"), 2, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.i_value[0], 2, 1)
        self.text_fields.i_value[0].editingFinished.connect(self.i_1_value_changed)

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>2</sub> Value"), 4, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.i_value[1], 4, 1)
        self.text_fields.i_value[1].editingFinished.connect(self.i_2_value_changed)

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("D Value"), 6, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.d_value, 6, 1)
        self.text_fields.d_value.editingFinished.connect(self.d_value_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Setpoint Temperature"), 0, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.setpoint_temperature, 0, 1)
        self.text_fields.setpoint_temperature.editingFinished.connect(self.setpoint_temperature_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Loop Time [ms]"), 1, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.loop_time, 1, 1)
        self.text_fields.loop_time.editingFinished.connect(self.loop_time_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Reference Resistor"), 2, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.reference_resistor, 2, 1)
        self.text_fields.reference_resistor.editingFinished.connect(self.reference_resistor_changed)
        model.tec_signals[self.laser].use_ntc.connect(self._update_resistor_visibility)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Max Power"), 3, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.max_power, 3, 1)
        self.text_fields.max_power.editingFinished.connect(self.max_power_changed)

        self.frames["Temperature"].layout().addWidget(self.temperature_display)

    def d_value_changed(self) -> None:
        self.controller.update_d_value(self.text_fields.d_value.text())

    def i_1_value_changed(self) -> None:
        self.controller.update_i_1_value(self.text_fields.i_value[0].text())

    def i_2_value_changed(self) -> None:
        self.controller.update_i_2_value(self.text_fields.i_value[1].text())

    def p_value_changed(self) -> None:
        self.controller.update_p_value(self.text_fields.p_value.text())

    def setpoint_temperature_changed(self) -> None:
        self.controller.update_setpoint_temperature(self.text_fields.setpoint_temperature.text())

    def loop_time_changed(self) -> None:
        self.controller.update_loop_time(self.text_fields.loop_time.text())

    def reference_resistor_changed(self) -> None:
        self.controller.update_reference_resistor(self.text_fields.reference_resistor.text())

    def max_power_changed(self) -> None:
        self.controller.update_max_power(self.text_fields.max_power.text())

    def _init_buttons(self) -> None:
        self.create_button(master=self.frames["Temperature"], title="Heat", slot=self.controller.set_heating)
        self.create_button(master=self.frames["Temperature"], title="Cool", slot=self.controller.set_cooling)
        config = self.create_configuration_buttons()
        self.frames["Configuration"].layout().addWidget(config, 3, 0)
