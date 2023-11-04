from dataclasses import dataclass
from typing import Union

from PyQt5 import QtWidgets, QtCore, QtGui
import qtwidgets

from minipti.gui import model, controller
from minipti.gui.view import helper
from minipti.gui.view import table


class SettingsWindow(QtWidgets.QMainWindow):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QMainWindow.__init__(self)
        self.parent = QtWidgets.QWidget()
        self.parent.setLayout(QtWidgets.QVBoxLayout())
        self.controller = settings_controller
        self.pti_configuration = PTIConfiguration(settings_controller)
        self.parent.layout().addWidget(self.pti_configuration)
        if self.controller.configuration.valve:
            self.valve_configuration = ValveConfiguration(settings_controller)
            self.parent.layout().addWidget(self.valve_configuration)
        if self.controller.configuration.measurement_settings:
            self.measurement_configuration = MeasurementSettings(settings_controller)
            self.parent.layout().addWidget(self.measurement_configuration)
        self.setCentralWidget(self.parent)
        self.setWindowTitle("Settings")
        self.setWindowIcon(QtGui.QIcon("minipti/gui/images/settings.svg"))


class SampleSettings(QtWidgets.QWidget):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QWidget.__init__(self)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.samples = QtWidgets.QLabel("8000 Samples")
        self.controller = settings_controller
        self.average_period = QtWidgets.QComboBox()
        self._init_average_period_box()
        model.signals.DAQ.samples_changed.connect(self.update_average_period)

    def _init_average_period_box(self) -> None:
        for i in range(1, 80):
            self.average_period.addItem(f"{i * 100 / 8000 * 1000} ms")
        for i in range(80, 320 + 1):
            self.average_period.addItem(f"{i * 100 / 8000 } s")
        self.average_period.setCurrentIndex(80 - 1)
        self.layout().addWidget(QtWidgets.QLabel("Averaging Time"))
        self.layout().addWidget(self.average_period)
        self.layout().addWidget(self.samples)
        self.average_period.currentIndexChanged.connect(self.update_samples)

    def update_average_period(self, samples: int) -> None:
        self.average_period.setCurrentIndex(samples // 100 - 1)

    def update_samples(self) -> None:
        text = self.average_period.currentText()
        if text[-2:] == "ms":
            self.samples.setText(f"{int((float(text[:-3]) / 1000) * 8000)} Samples")
        else:
            self.samples.setText(f"{int(float(text[:-2]) * 8000)} Samples")
        self.controller.update_average_period(self.samples.text())


class MeasurementOptions(QtWidgets.QWidget):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QWidget.__init__(self)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.controller = settings_controller
        self.common_mode_noise_rejection = qtwidgets.AnimatedToggle()
        self.common_mode_noise_rejection_label = QtWidgets.QLabel("Common Mode Noise Rejection")
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.layout().addWidget(self.common_mode_noise_rejection)
        self.common_mode_noise_rejection.stateChanged.connect(self.controller.update_common_mode_noise_reduction)
        self.common_mode_noise_rejection.setChecked(True)
        sub_layout.layout().addWidget(self.common_mode_noise_rejection_label)
        self.layout().addWidget(sub_layout)
        self.save_raw_data = qtwidgets.AnimatedToggle()
        self.common_mode_noise_rejection.setFixedSize(65, 50)
        self.save_raw_data.setFixedSize(65, 50)
        self.save_raw_data_label = QtWidgets.QLabel("Save Raw Data")
        self.save_raw_data.stateChanged.connect(self.controller.update_save_raw_data)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.layout().addWidget(self.save_raw_data)
        sub_layout.layout().addWidget(self.save_raw_data_label)
        self.layout().addWidget(sub_layout)


class MeasurementSettings(QtWidgets.QGroupBox):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QGroupBox.__init__(self)
        self.setTitle("Measurement Settings")
        self.setLayout(QtWidgets.QVBoxLayout())
        self.destination_folder_button: Union[QtWidgets.QPushButton, None] = None
        self.destination_folder_label = QtWidgets.QLabel("")
        self.sample_settings = SampleSettings(settings_controller)
        self.measurement_options = MeasurementOptions(settings_controller)
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.measurement_options)
        sublayout.layout().addWidget(self.sample_settings)
        self.layout().addWidget(sublayout)
        self.controller = settings_controller
        model.signals.GENERAL_PURPORSE.destination_folder_changed.connect(self.update_destination_folder)
        self._init_destination_folder()
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.save_settings = helper.create_button(sub_layout, title="Save Settings",
                                                  slot=self.controller.save_daq_settings)
        self.load_settings = helper.create_button(sub_layout, title="Load Settings",
                                                  slot=self.controller.load_daq_settings)
        self.layout().addWidget(sub_layout)

    def _init_destination_folder(self) -> None:
        self.destination_folder_button = helper.create_button(parent=self, title="Destination Folder",
                                                              slot=self.controller.set_destination_folder)
        self.layout().addWidget(self.destination_folder_label)

    @QtCore.pyqtSlot(str)
    def update_destination_folder(self, destionation_folder: str) -> None:
        self.destination_folder_label.setText(destionation_folder)


class ValveConfiguration(QtWidgets.QGroupBox):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QGroupBox.__init__(self)
        self.controller = settings_controller
        self.setLayout(QtWidgets.QGridLayout())
        self.automatic_valve_switch = qtwidgets.AnimatedToggle()
        self.automatic_valve_switch_label = QtWidgets.QLabel("Automatic Valve Switch")
        self.automatic_valve_switch.setFixedSize(65, 50)
        self.automatic_valve_switch.stateChanged.connect(self.controller.update_automatic_valve_switch)
        self.duty_cycle_valve = QtWidgets.QLabel("%")
        self.period_valve = QtWidgets.QLabel("s")
        self.duty_cycle_field = QtWidgets.QLineEdit()
        self.period_field = QtWidgets.QLineEdit()
        self._init_valves()
        self._init_signals()
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.layout().addWidget(self.automatic_valve_switch)
        sub_layout.layout().addWidget(self.automatic_valve_switch_label)
        self.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.save = helper.create_button(parent=sub_layout, title="Save Settings",
                                         slot=self.controller.save_valve_settings)
        self.load = helper.create_button(parent=sub_layout, title="Load Settings",
                                         slot=self.controller.load_valve_settings)
        self.layout().addWidget(sub_layout)
        self.setTitle("Valve Configuration")

    def _init_valves(self) -> None:
        self.layout().addWidget(self.automatic_valve_switch, 0, 0)
        self.layout().addWidget(QtWidgets.QLabel("Valve Period"), 1, 0)
        self.layout().addWidget(self.period_field, 1, 1)
        self.layout().addWidget(QtWidgets.QLabel("s"), 1, 2)
        self.layout().addWidget(QtWidgets.QLabel("Valve Duty Cycle"), 2, 0)
        self.layout().addWidget(self.duty_cycle_field, 2, 1)
        self.layout().addWidget(QtWidgets.QLabel("%"), 2, 2)

    def _init_signals(self) -> None:
        self.automatic_valve_switch.stateChanged.connect(self._automatic_switch_changed)
        self.period_field.editingFinished.connect(self._period_changed)
        self.duty_cycle_field.editingFinished.connect(self._duty_cycle_changed)
        model.signals.VALVE.period.connect(self.update_period)
        model.signals.VALVE.automatic_switch.connect(self.update_automatic_switch)
        model.signals.VALVE.duty_cycle.connect(self.update_duty_cycle)

    @QtCore.pyqtSlot(int)
    def update_period(self, period: int) -> None:
        self.period_field.setText(str(period))

    @QtCore.pyqtSlot(bool)
    def update_automatic_switch(self, automatic_switch: bool) -> None:
        self.automatic_valve_switch.setChecked(automatic_switch)

    @QtCore.pyqtSlot(int)
    def update_duty_cycle(self, duty_cycle: int) -> None:
        self.duty_cycle_field.setText(str(duty_cycle))

    def _automatic_switch_changed(self) -> None:
        self.controller.update_automatic_valve_switch(self.automatic_valve_switch.isChecked())

    def _period_changed(self) -> None:
        self.controller.update_valve_period(self.period_field.text())

    def _duty_cycle_changed(self) -> None:
        self.controller.update_valve_duty_cycle(self.duty_cycle_field.text())


@dataclass
class SettingsButtons:
    save: Union[QtWidgets.QPushButton, None] = None
    save_as: Union[QtWidgets.QPushButton, None] = None
    load: Union[QtWidgets.QPushButton, None] = None


class PTIConfiguration(QtWidgets.QGroupBox):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QGroupBox.__init__(self)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.controller = settings_controller
        self.buttons = SettingsButtons()
        self.algorithm_settings = table.Table(parent=self)
        self.layout().addWidget(self.algorithm_settings)
        self.algorithm_settings.setModel(self.controller.settings_table_model)
        self._init_buttons()
        self.setFixedSize(680, 270)
        self.setTitle("System Configuration")
        if not self.controller.configuration.system_settings.response_phases:
            self.algorithm_settings.hideRow(3)
        model.signals.CALCULATION.settings_pti.connect(self.update_table)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.buttons.save_settings = helper.create_button(parent=sub_layout, title="Save Settings",
                                                          slot=self.controller.save_pti_settings)
        self.buttons.save_settings_as = helper.create_button(parent=sub_layout, title="Save Settings As",
                                                             slot=self.controller.save_pti_settings_as)
        self.buttons.load_settings = helper.create_button(parent=sub_layout, title="Load Settings",
                                                          slot=self.controller.load_pti_settings)
        self.layout().addWidget(sub_layout)

    @QtCore.pyqtSlot()
    def update_table(self) -> None:
        self.algorithm_settings.update()
