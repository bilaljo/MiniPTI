@dataclass
class HomeButtons:
    run_measurement: Union[QtWidgets.QPushButton, None] = None
    settings: Union[QtWidgets.QPushButton, None] = None
    utilities: Union[QtWidgets.QPushButton, None] = None


class Home(QtWidgets.QTabWidget):
    def __init__(self, home_controller: controller.interface.Home):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = home_controller
        self.dc_signals = plots.DC()
        self.pti_signal = plots.PTISignal()
        self.buttons = HomeButtons()
        self._init_buttons()
        self._init_signals()
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.dc_signals.window)
        sublayout.layout().addWidget(self.pti_signal.window)
        self.layout().addWidget(sublayout, 0, 0)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.buttons.run_measurement = helper.create_button(parent=sub_layout, title="Run Measurement",
                                                            slot=self.controller.enable_motherboard)
        self.buttons.settings = helper.create_button(parent=sub_layout, title="Settings",
                                                     slot=self.controller.show_settings)
        self.buttons.utilities = helper.create_button(parent=sub_layout, title="Utilities",
                                                      slot=self.controller.show_utilities)
        self.layout().addWidget(sub_layout, 1, 0)
        # self.create_button(master=sub_layout, title="Clean Air", slot=self.controller.update_bypass)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        helper.toggle_button(state, self.buttons.run_measurement)

    # @QtCore.pyqtSlot(bool)
    # def update_clean_air(self, state: bool) -> None:
    #    helper.toggle_button(state, self.buttons["Clean Air"])

    def _init_signals(self) -> None:
        model.signals.daq_running.connect(self.update_run_measurement)
