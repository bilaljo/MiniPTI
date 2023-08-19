from dataclasses import dataclass
from typing import Union, Callable

from PyQt5 import QtWidgets, QtCore

from minipti.gui import model, controller
from minipti.gui.view import helper
from minipti.gui.view import table


class SaveSettings(QtWidgets.QGroupBox):
    def __init__(self, set_destination_folder: Callable[[str], None]):
        QtWidgets.QGroupBox.__init__(self)
        self.setTitle("Save Settings")
        self.setLayout(QtWidgets.QGridLayout())
        self.save_pti_data = QtWidgets.QCheckBox("Save PTI Data")
        self.save_tec_data = QtWidgets.QCheckBox("Save TEC Data")
        self.save_laser_data = QtWidgets.QCheckBox("Save Laser Data")
        self.save_bms_data = QtWidgets.QCheckBox("Save BMS Data")
        self.destination_folder = QtWidgets.QLabel("")
        self._init_destination_folder(set_destination_folder)
        model.signals.destination_folder_changed.connect(self.update_destination_folder)
        self._init_checkboxes()

    def _init_checkboxes(self) -> None:
        self.layout().addWidget(self.save_pti_data, 0, 3)
        self.save_pti_data.setChecked(True)
        self.layout().addWidget(self.save_tec_data, 1, 3)
        self.save_tec_data.setChecked(True)
        self.layout().addWidget(self.save_laser_data, 2, 3)
        self.save_laser_data.setChecked(True)
        self.layout().addWidget(self.save_bms_data, 3, 3)
        self.save_bms_data.setChecked(True)

    def _init_destination_folder(self, set_destination_folder: Callable[[None], None]) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.destination_folder = helper.create_button(parent=sub_layout, title="Destination Folder",
                                                       slot=set_destination_folder)
        sub_layout.layout().addWidget(self.destination_folder)
        sub_layout.layout().addWidget(self.destination_folder)
        self.layout().addWidget(sub_layout, 0, 0, 2, 2)

    @QtCore.pyqtSlot(str)
    def update_destination_folder(self, destionation_folder: str) -> None:
        self.destination_folder.setText(destionation_folder)


@dataclass
class SettingsFrames:
    pti_configuration: Union[QtWidgets.QGroupBox, None] = None
    measurement: Union[QtWidgets.QGroupBox, None] = None
    valve: Union[QtWidgets.QGroupBox, None] = None
    file_path: Union[QtWidgets.QGroupBox, None] = None
    tec_settings:  Union[QtWidgets.QGroupBox, None] = None
    laser_settings: Union[QtWidgets.QGroupBox, None] = None
    pti_mode: Union[QtWidgets.QGroupBox, None] = None
    interferometric_mode: Union[QtWidgets.QGroupBox, None] = None


@dataclass
class SettingsButtons:
    save_pti_settings: Union[QtWidgets.QPushButton, None] = None
    save_pti_settings_as: Union[QtWidgets.QPushButton, None] = None
    load_pti_settings: Union[QtWidgets.QPushButton, None] = None
    save_motherboard_settings: Union[QtWidgets.QPushButton, None] = None
    save_motherboard_settings_as: Union[QtWidgets.QPushButton, None] = None
    load_motherboard_settings: Union[QtWidgets.QPushButton, None] = None


@dataclass
class SettingsCheckButtons:
    save_raw_data: QtWidgets.QCheckBox
    common_mode_noise_rejection: QtWidgets.QCheckBox


class SettingsTab(QtWidgets.QTabWidget):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = settings_controller
        self.frames = SettingsFrames()
        self.buttons = SettingsButtons()
        self.algorithm_settings = table.Table(parent=self.frames.pti_configuration)
        self.algorithm_settings.setModel(self.controller.settings_table_model)
        self.check_boxes = SettingsCheckButtons(QtWidgets.QCheckBox("Save Raw Data"),
                                                QtWidgets.QCheckBox("Common Mode Noise Rejection"))
        self.automatic_valve_switch = QtWidgets.QCheckBox("Automatic Valve Switch")
        self.duty_cycle_valve = QtWidgets.QLabel("%")
        self.period_valve = QtWidgets.QLabel("s")
        self.duty_cycle_field = QtWidgets.QLineEdit()
        self.period_field = QtWidgets.QLineEdit()
        self.average_period = QtWidgets.QComboBox()
        self.save_settings = SaveSettings(self.controller.set_destination_folder)
        self.samples = QtWidgets.QLabel("8000 Samples")
        self._init_frames()
        self._init_average_period_box()
        self.frames.pti_configuration.layout().addWidget(self.algorithm_settings)
        self._init_buttons()
        self._init_valves()
        model.signals.valve_change.connect(self.update_valve)

    def update_samples(self) -> None:
        text = self.average_period.currentText()
        if text[-2:] == "ms":
            self.samples.setText(f"{int((float(text[:-3]) / 1000) * 8000)} Samples")
        else:
            self.samples.setText(f"{int(float(text[:-2]) * 8000)} Samples")
        self.controller.update_average_period(self.samples.text())

    @QtCore.pyqtSlot(model.Valve)
    def update_valve(self, valve: model.Valve) -> None:
        self.duty_cycle_field.setText(str(valve.duty_cycle))
        self.period_field.setText(str(valve.period))
        self.automatic_valve_switch.setChecked(valve.automatic_switch)

    def _init_average_period_box(self) -> None:
        for i in range(1, 80):
            self.average_period.addItem(f"{i * 100 / 8000 * 1000} ms")
        for i in range(80, 320 + 1):
            self.average_period.addItem(f"{i * 100 / 8000 } s")
        self.average_period.setCurrentIndex(80 - 1)
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QVBoxLayout())
        sublayout.layout().addWidget(QtWidgets.QLabel("Averaging Time"))
        sublayout.layout().addWidget(self.average_period)
        sublayout.layout().addWidget(self.samples)
        self.frames.measurement.layout().addWidget(sublayout)
        self.average_period.currentIndexChanged.connect(self.update_samples)

    def _init_frames(self) -> None:
        self.frames.pti_configuration = helper.create_frame(parent=self, title="Configuration", x_position=0,
                                                            y_position=0, x_span=2)
        self.frames.file_path = helper.create_frame(parent=self, title="File Path", x_position=3, y_position=0)
        self.frames.measurement = helper.create_frame(parent=self, title="Measurement", x_position=2, y_position=0)
        self.frames.valve = helper.create_frame(parent=self, title="Valve", x_position=0, y_position=1, x_span=1)
        self.layout().addWidget(self.save_settings, 1, 1)
        self.frames.tec_settings = helper.create_frame(parent=self, title="TEC", x_position=2, y_position=1, y_span=4)
        self.frames.laser_settings = helper.create_frame(parent=self, title="Laser", x_position=3, y_position=1)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget(parent=self.frames.pti_configuration)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.pti_configuration.layout().addWidget(sub_layout)
        self.buttons.save_settings = helper.create_button(parent=sub_layout, title="Save Settings",
                                                          slot=self.controller.save_settings)
        self.buttons.save_settings_as = helper.create_button(parent=sub_layout, title="Save Settings As",
                                                             slot=self.controller.save_settings_as)
        self.buttons.load_settings = helper.create_button(parent=sub_layout, title="Load Settings",
                                                          slot=self.controller.load_settings)
        self.frames.measurement.layout().addWidget(self.check_boxes.save_raw_data)
        self.frames.measurement.layout().addWidget(self.check_boxes.common_mode_noise_rejection)
        sub_layout = QtWidgets.QWidget(parent=self.frames.file_path)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.file_path.layout().addWidget(sub_layout)

    def _init_valves(self) -> None:
        sub_layout = QtWidgets.QWidget(parent=self.frames.valve)
        sub_layout.setLayout(QtWidgets.QGridLayout())
        sub_layout.layout().addWidget(self.automatic_valve_switch, 0, 0)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Period"), 1, 0)
        sub_layout.layout().addWidget(self.period_field, 1, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("s"), 1, 2)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Duty Cycle"), 2, 0)
        sub_layout.layout().addWidget(self.duty_cycle_field, 2, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("%"), 2, 2)
        self.frames.valve.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget(parent=self.frames.valve)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.valve.layout().addWidget(sub_layout)

        self.automatic_valve_switch.stateChanged.connect(self._automatic_switch_changed)
        self.period_field.editingFinished.connect(self._period_changed)
        self.duty_cycle_field.editingFinished.connect(self._duty_cycle_changed)

    def _automatic_switch_changed(self) -> None:
        self.controller.update_automatic_valve_switch(self.automatic_valve_switch.isChecked())

    def _period_changed(self) -> None:
        self.controller.update_valve_period(self.period_field.text())

    def _duty_cycle_changed(self) -> None:
        self.controller.update_valve_duty_cycle(self.duty_cycle_field.text())
