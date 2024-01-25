import abc
import logging
import os
import threading
import typing
from dataclasses import dataclass

try:
    import qdarktheme
except ModuleNotFoundError:
    pass

from PyQt5 import QtWidgets, QtCore, QtGui
from overrides import override

import minipti
from minipti.gui import model
from minipti.gui import view
from minipti.gui.controller import interface


@dataclass
class Controllers(interface.Controllers):
    main_application: "MainApplication"
    toolbar: "Toolbar"
    statusbar: "Statusbar"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: "PumpLaser"
    probe_laser: "ProbeLaser"
    tec: list["Tec"]

    @property
    def configuration(self) -> model.configuration.GUI:
        return self.main_application.configuration


class MainApplication(interface.MainApplication):
    def __init__(self, argv=""):
        interface.MainApplication.__init__(self, argv)
        splash = QtWidgets.QSplashScreen(QtGui.QPixmap(f"{minipti.MODULE_PATH}/gui/images/loading_screen.jpg"))
        splash.show()
        self.setStyle("Fusion")
        settings_controller = Settings()
        utilities_controller = Utilities()
        self._controllers: Controllers = Controllers(
            main_application=self,
            toolbar=Toolbar(settings_controller, utilities_controller),
            statusbar=Statusbar(),
            settings=settings_controller,
            utilities=utilities_controller,
            pump_laser=PumpLaser(),
            probe_laser=ProbeLaser(),
            tec=[
                Tec(laser=model.serial_devices.Tec.PUMP_LASER),
                Tec(laser=model.serial_devices.Tec.PROBE_LASER)
                ]
            )
        self.logging_model = model.general_purpose.Logging()
        self.view = view.api.MainWindow(self.controllers)
        self.controllers.toolbar.view = self.view
        model.signals.GENERAL_PURPORSE.theme_changed.connect(self.update_theme)
        threading.Thread(
            target=model.general_purpose.theme_observer,
            daemon=True
        ).start()
        self.controllers.toolbar.init_devices()
        self.setFont(QtGui.QFont('Arial', 11))
        splash.finish(self.view)
        splash.close()
        # threading.excepthook = self.thread_exception

    @override
    def emergency_stop(self) -> None:
        model.serial_devices.TOOLS.pump_laser.enabled = False
        model.serial_devices.TOOLS.probe_laser.enabled = False

    @override
    def close(self) -> None:
        model.serial_devices.DRIVER.motherboard.clear()
        model.serial_devices.DRIVER.tec.clear()
        model.serial_devices.DRIVER.laser.clear()

    @QtCore.pyqtSlot(str)
    def update_theme(self, theme: str) -> None:
        try:
            qdarktheme.setup_theme(theme.casefold())
        except ModuleNotFoundError:
            theme = "Light"
        for plot in self.view.plots:  # type: view.plots.Plotting | list
            try:
                plot.update_theme(theme)
            except AttributeError:  # list of plots
                try:
                    for sub_plot in plot:  # type: view.plots.Plotting
                        sub_plot.update_theme(theme)
                except TypeError:
                    pass
        self.view.plots.measurement.pti.update_theme(theme)
        self.view.plots.measurement.sensitivity.update_theme(theme)
        self.view.plots.interferometrie.dc_plot.update_theme(theme)
        self.view.plots.interferometrie.phase_plot.update_theme(theme)
        self.view.plots.characterisation.amplitudes.update_theme(theme)
        self.view.plots.characterisation.output_phase.update_theme(theme)
        self.view.plots.characterisation.symmetry.update_theme(theme)

    @property
    @override
    def controllers(self) -> Controllers:
        return self._controllers

    def thread_exception(self, args) -> None:
        if args.exc_type == KeyError:
            QtWidgets.QMessageBox.critical(
                self.view, "File Error",
                "Invalid file given or missing headers."
            )
        elif args.exc_type == TimeoutError:
            QtWidgets.QMessageBox.critical(
                self.view,
                "Timeout Error",
                "Timeout Error"
            )
        else:
            QtWidgets.QMessageBox.critical(
                self.view, "Error",
                f"{args.exc_type} error occurred."
            )


def _get_file_path(
        parent: QtWidgets.QWidget,
        dialog_name: str,
        last_file_path: str,
        files: str
    ) -> tuple[str, str]:
    file_path = QtWidgets.QFileDialog.getOpenFileName(
        parent,
        directory=last_file_path,
        caption=dialog_name,
        filter=files
    )
    if file_path[0]:
        last_file_path = file_path[0]
    return file_path[0], last_file_path


class Toolbar(interface.Toolbar):
    def __init__(
            self,
            settings_controller: "Settings",
            utilities_controller: "Utilities"
    ):
        self.view: view.api.MainWindow | = None
        self.settings_controller = settings_controller
        self.utilities_controller = utilities_controller
        self._destination_folder = model.processing.DestinationFolder()
        self.calculation_model = settings_controller.calculation_model
        self.running = False
        model.serial_devices.TOOLS.daq.fire_configuration_change()

    @override
    def on_run(self) -> None:
        self.running = not self.running
        model.serial_devices.DRIVER.laser.sampling = self.running
        model.serial_devices.DRIVER.tec.sampling = self.running
        model.serial_devices.DRIVER.motherboard.sampling = self.running
        if model.configuration.GUI.on_run.pump_laser.laser_driver:
            model.serial_devices.TOOLS.pump_laser.enabled = self.running
        if model.configuration.GUI.on_run.probe_laser.laser_driver:
            model.serial_devices.TOOLS.probe_laser.enabled = self.running
        if model.configuration.GUI.on_run.pump_laser.tec_driver:
            model.serial_devices.TOOLS.tec[model.serial_devices.Tec.PUMP_LASER].enabled = self.running
        if model.configuration.GUI.on_run.probe_laser.tec_driver:
            model.serial_devices.TOOLS.tec[model.serial_devices.Tec.PROBE_LASER].enabled = self.running
        if model.configuration.GUI.on_run.pump:
            model.serial_devices.TOOLS.pump.enabled = self.running
        if model.configuration.GUI.on_run.DAQ:
            self.enable_daq()

    @override
    def enable_daq(self) -> None:
        if not model.serial_devices.DRIVER.motherboard.connected:
            QtWidgets.QMessageBox.critical(
                self.view,
                "IO Error",
                "Cannot enable Motherboard. Motherboard is not connected."
            )
            logging.error("Cannot enable Motherboard")
            logging.warning("Motherboard is not connected")
        else:
            if self.running:
                model.serial_devices.TOOLS.daq.running = True
                self.calculation_model.process_daq_data()
            else:
                model.serial_devices.TOOLS.daq.running = False
            text = "Enabled" if self.running else "Disabled"
            logging.debug("%s Motherboard", text)

    @override
    def shutdown(self) -> None:
        model.serial_devices.TOOLS.bms.shutdown_procedure()

    @override
    def show_settings(self) -> None:
        self.settings_controller.view.show()

    @override
    def show_utilities(self) -> None:
        self.utilities_controller.view.show()

    @property
    @override
    def destination_folder(self) -> model.processing.DestinationFolder:
        return self._destination_folder

    @override
    def update_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(
            self.view,
            "Destination Folder",
            self.destination_folder.folder,
            QtWidgets.QFileDialog.ShowDirsOnly
        )
        if destination_folder:
            self.destination_folder.folder = destination_folder

    @override
    def init_devices(self) -> None:
        def find_and_connect():
            self.find_devices()
            self.connect_devices()

        threading.Thread(
            target=find_and_connect,
            name="Find and Connect Devices Thread",
            daemon=True
        ).start()

    @override
    def find_devices(self) -> None:
        if model.configuration.GUI.connect.motherboard:
            try:
                if not model.serial_devices.DRIVER.motherboard.is_found:
                    model.serial_devices.DRIVER.motherboard.find_port()
            except OSError:
                logging.error("Could not find Motherboard")
        if model.configuration.GUI.connect.laser_driver:
            try:
                if not model.serial_devices.DRIVER.laser.is_found:
                    model.serial_devices.DRIVER.laser.find_port()
            except OSError:
                logging.error("Could not find Laser Driver")
        if model.configuration.GUI.connect.tec_driver:
            try:
                if not model.serial_devices.DRIVER.tec.is_found:
                    model.serial_devices.DRIVER.tec.find_port()
            except OSError:
                logging.error("Could not find TEC Driver")

    @override
    def connect_devices(self) -> None:
        if not model.serial_devices.DRIVER.motherboard.is_open and \
                model.serial_devices.DRIVER.motherboard.is_found:
            try:
                model.serial_devices.DRIVER.motherboard.open()
                model.serial_devices.DRIVER.motherboard.run()
                model.serial_devices.TOOLS.valve.process_measured_data()
                model.serial_devices.TOOLS.bms.process_measured_data()
                model.serial_devices.TOOLS.valve.automatic_valve_change()
            except OSError:
                logging.error("Could not connect with Motherboard")
        if not model.serial_devices.DRIVER.laser.is_open and\
                model.serial_devices.DRIVER.laser.is_found:
            try:
                model.serial_devices.DRIVER.laser.open()
                model.serial_devices.TOOLS.pump_laser.start_up()
                model.serial_devices.TOOLS.probe_laser.start_up()
                model.serial_devices.DRIVER.laser.run()
                model.serial_devices.TOOLS.pump_laser.process_measured_data()
            except OSError:
                logging.error("Could not connect with Laser Driver")
        if not model.serial_devices.DRIVER.tec.is_open and\
                model.serial_devices.DRIVER.tec.is_found:
            try:
                model.serial_devices.DRIVER.tec.open()
                model.serial_devices.DRIVER.tec.run()
                model.serial_devices.TOOLS.tec[0].process_measured_data()
            except OSError:
                logging.error("Could not connect with TEC Driver")

    @override
    def change_valve(self) -> None:
        model.serial_devices.TOOLS.valve.bypass = not model.serial_devices.TOOLS.valve.bypass

    @override
    def enable_pump(self) -> None:
        model.serial_devices.TOOLS.pump.enabled = not model.serial_devices.TOOLS.pump.enabled


class Statusbar(interface.Statusbar):
    def __init__(self):
        self._view = view.general_purpose.StatusBar(self)
        self.bms = view.general_purpose.BatteryWindow()
        self.view.showMessage(str(minipti.MODULE_PATH.parent))

    @property
    @override
    def view(self) -> view.general_purpose.StatusBar:
        return self._view

    @override
    def show_bms(self) -> None:
        self.bms.show()

    @override
    def update_destination_folder(self, folder: str) -> None:
        self.view.clearMessage()
        self.view.showMessage(folder)


class Settings(interface.Settings):
    def __init__(self):
        interface.Settings.__init__(self)
        self.calculation_model = model.processing.LiveCalculation()
        self._settings_table = model.processing.SettingsTable()
        self.view = view.settings.SettingsWindow(self)
        self.last_file_path = os.getcwd()
        if model.configuration.GUI.settings.pump:
            self.view.pump_configuration.enable.setChecked(True)
        self.fire_configuration_change()

    @override
    def fire_configuration_change(self) -> None:
        model.serial_devices.TOOLS.daq.fire_configuration_change()
        model.serial_devices.TOOLS.valve.fire_configuration_change()
        model.serial_devices.TOOLS.pump.fire_configuration_change()

    @property
    @override
    def settings_table_model(self) -> model.processing.SettingsTable:
        return self._settings_table

    @override
    def update_common_mode_noise_reduction(self, state: bool):
        self.calculation_model.set_common_mode_noise_reduction(state)

    @override
    def update_save_raw_data(self, state: bool):
        self.calculation_model.set_raw_data_saving(state)

    @override
    def save_pti_settings(self) -> None:
        self.settings_table_model.save()

    @override
    def save_pti_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="CSV File", file_extension="csv",
                            name="Algorithm Configuration")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.save()

    @override
    def load_pti_settings(self):
        file_path, self.last_file_path = _get_file_path(self.view, "Load SettingsTable", self.last_file_path,
                                                        "CSV File (*.csv);;"
                                                        " TXT File (*.txt);; All Files (*);;")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.load()

    @override
    def save_daq_settings(self) -> None:
        model.serial_devices.TOOLS.daq.save_configuration()

    def save_daq_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON", file_extension="json",
                            name="DAQ Configuration")
        if file_path:
            model.serial_devices.TOOLS.daq.config_path = file_path
            model.serial_devices.TOOLS.daq.save_configuration()

    @override
    def load_daq_settings(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Laser Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            model.serial_devices.TOOLS.daq.config_path = config_path
        else:
            return
        model.serial_devices.TOOLS.daq.load_configuration()

    @override
    def save_valve_settings(self) -> None:
        model.serial_devices.TOOLS.valve.save_configuration()

    def save_valve_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON", file_extension="json",
                            name="Valve Configuration")
        if file_path:
            model.serial_devices.TOOLS.valve.config_path = file_path
            model.serial_devices.TOOLS.valve.save_configuration()

    @override
    def load_valve_settings(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Valve", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            model.serial_devices.TOOLS.valve.config_path = config_path
        else:
            return
        model.serial_devices.TOOLS.valve.load_configuration()

    @override
    def save_pump_settings(self) -> None:
        model.serial_devices.TOOLS.pump.save_configuration()

    @override
    def load_pump_settings(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Pump", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            model.serial_devices.TOOLS.pump.config_path = config_path
        else:
            return
        model.serial_devices.TOOLS.pump.load_configuration()

    @override
    def update_valve_period(self, period: str) -> None:
        try:
            period = _string_to_number(self.view, period, cast=int)
        except ValueError:
            period = 600
        try:
            model.serial_devices.TOOLS.valve.period = period
        except ValueError as error:
            info_text = "Value must be a positive integer"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    @override
    def update_valve_duty_cycle(self, duty_cycle: str) -> None:
        try:
            duty_cycle = _string_to_number(self.view, duty_cycle, cast=int)
        except ValueError:
            duty_cycle = 50
        try:
            model.serial_devices.TOOLS.valve.duty_cycle = duty_cycle
        except ValueError as error:
            info_text = "Value must be an integer between 0 and 100"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    @override
    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        model.serial_devices.TOOLS.valve.automatic_switch = automatic_valve_switch

    @override
    def update_bypass(self) -> None:
        model.serial_devices.TOOLS.motherboard.bypass = not model.serial_devices.TOOLS.motherboard.bypass

    @override
    def update_flow_rate(self, flow_rate: str) -> None:
        try:
            flow_rate = _string_to_number(self.view, flow_rate, cast=float)
        except ValueError:
            flow_rate = 50
        try:
            model.serial_devices.TOOLS.pump.flow_rate = flow_rate
        except ValueError as error:
            info_text = "Value must be an floating number between 0 and 100"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Pump Error", f"{str(error)}. {info_text}")

    @override
    def enable_pump(self, enable: bool) -> None:
        if enable:
            model.serial_devices.TOOLS.pump.enable = True
            model.serial_devices.TOOLS.pump.enable_pump()
        else:
            model.serial_devices.TOOLS.pump.enable = False
            model.serial_devices.TOOLS.pump.disable_pump()

    @override
    def enable_pump_on_run(self) -> None:
        model.serial_devices.TOOLS.pump.enable_on_run = not model.serial_devices.TOOLS.pump.enable_on_run

    @override
    def update_sample_setting(self) -> None:
        sample_settings = self.view.measurement_configuration.sample_settings
        if model.serial_devices.TOOLS.daq.running:
            logging.error("Cannot change sample rate while DAQ is running")
            sample_settings.average_period.setCurrentIndex(sample_settings.last_period)
            return
        self.update_samples(sample_settings.average_period.currentText())

    def update_samples(self, average_period: str) -> None:
        if average_period[-2:] == "ms":
            samples = int((float(average_period[:-3]) / 1000) * 8000)
        else:
            samples = int(float(average_period[:-2]) * 8000)
        model.serial_devices.TOOLS.daq.number_of_samples = samples
        self.calculation_model.pti.decimation.average_period = samples
        self.view.measurement_configuration.sample_settings.samples.setText(f"{samples} Samples")


class Utilities(interface.Utilities):
    def __init__(self):
        self.view = view.utilities.UtilitiesWindow(self)
        self.calculation_model = model.processing.OfflineCalculation()
        self.last_file_path = os.getcwd()
        model.signals.CALCULATION.dc_signals.connect(view.plots.dc_offline)
        model.signals.CALCULATION.inversion.connect(view.plots.pti_signal_offline)
        model.signals.CALCULATION.interferometric_phase.connect(view.plots.interferometric_phase_offline)
        model.signals.CALCULATION.lock_in_phases.connect(view.plots.lock_in_phase_offline)
        model.signals.CALCULATION.characterization.connect(view.plots.interferometer_characterisation)
        # model.theme_signal.changed.connect(view.utilities.update_matplotlib_theme)

    @override
    def calculate_decimation(self) -> None:
        decimation_file_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                   "HDF5 File (*.hdf5);; All Files (*)")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation,
                         args=[decimation_file_path]).start()

    @override
    def plot_dc(self) -> None:
        try:
            decimation_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                  "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
            if decimation_path:
                model.processing.process_dc_data(decimation_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def calculate_interferometry(self) -> None:
        interferometry_path, self.last_file_path = _get_file_path(self.view, "Decimation File",
                                                                  self.last_file_path,
                                                                  "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not interferometry_path:
            return
        threading.Thread(target=self.calculation_model.calculate_interferometry, args=[interferometry_path]).start()

    @override
    def calculate_response_phases(self) -> None:
        decimation_path, self.last_file_path = _get_file_path(self.view, "Decimation File",
                                                              self.last_file_path,
                                                              "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not decimation_path:
            return
        self.calculation_model.calculate_response_phases(decimation_path)

    @override
    def calculate_pti_inversion(self) -> None:
        inversion_path, self.last_file_path = _get_file_path(self.view, "Decimation File", self.last_file_path,
                                                             "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion, args=[inversion_path]).start()

    @override
    def plot_inversion(self) -> None:
        try:
            inversion_path, self.last_file_path = _get_file_path(self.view, "Inversion", self.last_file_path,
                                                                 "CSV File (*.csv);; TXT File (*.txt);;"
                                                                 " All Files (*)")
            if inversion_path:
                model.processing.process_inversion_data(inversion_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def plot_interferometric_phase(self) -> None:
        try:
            interferometric_phase_path, self.last_file_path = _get_file_path(self.view, "Inversion",
                                                                             self.last_file_path,
                                                                             "CSV File (*.csv);; TXT File (*.txt);;"
                                                                             " All Files (*)")
            if interferometric_phase_path:
                model.processing.process_interferometric_phase_data(interferometric_phase_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def plot_lock_in_phases(self) -> None:
        try:
            lock_in_phases, self.last_file_path = _get_file_path(self.view, "Lock In Phases",
                                                                 self.last_file_path,
                                                                 "CSV File (*.csv);; TXT File (*.txt);;"
                                                                 " All Files (*)")
            if lock_in_phases:
                model.processing.process_lock_in_phases_data(lock_in_phases)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def plot_characterisation(self) -> None:
        try:
            characterisation, self.last_file_path = _get_file_path(
                self.view,
                "Characterisation",
                self.last_file_path,
                "CSV File (*.csv);; TXT File (*.txt);;"
                " All Files (*)"
            )
            if characterisation:
                model.processing.process_characterization_data(characterisation)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def calculate_characterisation(self) -> None:
        characterisation_path, self.last_file_path = _get_file_path(self.view, "Characterisation",
                                                                    self.last_file_path,
                                                                    "CSV File (*.csv);; TXT File (*.txt);;"
                                                                    " All Files (*)")
        if not characterisation_path:
            return
        threading.Thread(
            target=self.calculation_model.calculate_characterisation,
            args=[characterisation_path]
        ).start()

    @override
    def plot_characterisation(self) -> None:
        try:
            characterization_path, self.last_file_path = _get_file_path(
                self.view, "Characterization",
                self.last_file_path,
                "CSV File (*.csv);; TXT File (*.txt);;"
                " All Files (*)"
            )
            if characterization_path:
                model.processing.process_characterization_data(characterization_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")


T = typing.TypeVar("T")


def _string_to_number(parent: QtWidgets.QWidget, string_number: str, cast: typing.Callable[[str], T]) -> T:
    try:
        return cast(string_number)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        QtWidgets.QMessageBox.critical(parent, "Value Error",
                                       "Could not apply new value. Invalid symbols encountered.")
        raise ValueError


class Laser(interface.Driver):
    def __init__(self):
        interface.Driver.__init__(self)
        self.last_file_path = os.getcwd()
        self.laser = model.serial_devices.TOOLS.pump_laser

    def load_configuration(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Laser Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.laser.config_path = config_path
        else:
            return
        self.laser.load_configuration()
        self.fire_configuration_change()

    def save_configuration(self) -> None:
        self.laser.save_configuration()

    def save_configuration_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON File", file_extension="json",
                            name="Laser Configuration")
        if file_path:
            self.laser.config_path = file_path  # The actual file path
            self.laser.save_configuration()

    def apply_configuration(self) -> None:
        self.laser.apply_configuration()

    @abc.abstractmethod
    def fire_configuration_change(self) -> None:
        """
        By initialisation of the Laser Driver Object (on which the laser model relies) the
        configuration is already set and do not fire events to update the GUI. This function is
        hence only called once to manually activate the firing.
        """


class PumpLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self._view = view.hardware.PumpLaser(self)
        self.laser = model.serial_devices.TOOLS.pump_laser

    @property
    @override
    def view(self) -> view.hardware.PumpLaser:
        return self._view

    @override
    def enable(self) -> None:
        if not self.laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Pump Laser. Laser Driver is not connected.")
            logging.error("Cannot enable Pump Laser")
            logging.warning("Laser Driver is not connected")
        else:
            if not self.laser.enabled:
                self.laser.enabled = True
            else:
                self.laser.enabled = False
            logging.debug(f"{'Enabled' if self.laser.enabled else 'Disabled'} Pump Laser")

    def update_driver_voltage(self, bits: int) -> None:
        if bits != self.laser.driver_bits:
            self.laser.driver_bits = bits

    def update_current_dac1(self, bits: int) -> None:
        if self.laser.current_bits_dac_2 != bits:
            self.laser.current_bits_dac_1 = bits

    def update_current_dac2(self, bits: int) -> None:
        if self.laser.current_bits_dac_1 != bits:
            self.laser.current_bits_dac_2 = bits

    def update_dac1(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_1_matrix, channel, mode)

        return set_matrix

    def update_dac2(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_2_matrix, channel, mode)

        return set_matrix

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class ProbeLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self.laser = model.serial_devices.TOOLS.probe_laser
        self._view = view.hardware.ProbeLaser(self)

    @property
    @override
    def view(self) -> view.hardware.ProbeLaser:
        return self._view

    @override
    def enable(self) -> None:
        if not self.laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Probe Laser. Laser Driver is not connected.")
            logging.error("Cannot enable Probe Laser")
            logging.warning("Laser Driver is not connected")
        else:
            if not self.laser.enabled:
                self.laser.enabled = True
            else:
                self.laser.enabled = False
            logging.debug(f"{'Enabled' if self.laser.enabled else 'Disabled'} Probe Laser")

    def update_max_current_probe_laser(self, max_current: str) -> None:
        try:
            new_max_current = _string_to_number(self.view, max_current, cast=float)
        except ValueError:
            return
        self.laser.probe_laser_max_current = new_max_current

    def update_photo_gain(self, value: int) -> None:
        if self.laser.photo_diode_gain != value + 1:
            self.laser.photo_diode_gain = value + 1

    def update_probe_laser_mode(self, index: int) -> None:
        self.laser.probe_laser_mode = index

    def update_current_probe_laser(self, bits: int) -> None:
        effective_bits: int = model.serial_devices.ProbeLaser.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class Tec(interface.Driver):
    def __init__(self, laser: int):
        self.tec = model.serial_devices.TOOLS.tec[laser]
        self.laser = laser
        self._view = view.hardware.Tec(self, laser)
        self.last_file_path = os.getcwd()

    @property
    @override
    def view(self) -> view.hardware.Tec:
        return self._view

    @override
    def save_configuration_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON File", file_extension="json", name="TEC Configuration")
        if file_path:
            self.tec.config_path = file_path  # The actual file path
            self.tec.save_configuration()

    @override
    def save_configuration(self) -> None:
        self.tec.save_configuration()

    @override
    def load_configuration(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "TEC Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.tec.config_path = config_path
        else:
            return
        self.tec.load_configuration()
        self.fire_configuration_change()

    @override
    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

    @override
    def enable(self) -> None:
        if not self.tec.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Pump Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Pump Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.tec.enabled:
                self.tec.enabled = True
            else:
                self.tec.enabled = False
            logging.debug(f"{'Enabled' if self.tec.enabled else 'Disabled'} Tec Driver of %s",
                          "Pump Laser" if self.laser == model.serial_devices.Tec.PUMP_LASER else "Probe Laser")

    def update_d_gain(self, d_gain: str) -> None:
        try:
            self.tec.d_gain = _string_to_number(self.view, d_gain, cast=float)
            print(self.tec.d_gain)
        except ValueError:
            self.tec.d_gain = 0

    def update_i_gain(self, i_gain: str) -> None:
        try:
            self.tec.i_gain = _string_to_number(self.view, i_gain, cast=float)
        except ValueError:
            self.tec.i_gain = 0

    def update_p_gain(self, p_gain: str) -> None:
        try:
            self.tec.p_value = _string_to_number(self.view, p_gain, cast=float)
        except ValueError:
            self.tec.p_value = 0

    def update_setpoint_temperature(self, setpoint_temperature: str) -> None:
        try:
            self.tec.setpoint_temperature = _string_to_number(self.view, setpoint_temperature, cast=float)
        except ValueError:
            self.tec.setpoint_temperature = model.serial_devices.Tec.ROOM_TEMPERATURE

    def update_loop_time(self, loop_time: str) -> None:
        self.tec.loop_time = _string_to_number(self.view, loop_time, cast=int)

    def update_max_power(self, max_power: str) -> None:
        try:
            self.tec.max_power = _string_to_number(self.view, max_power, cast=float)
        except ValueError:
            self.tec.max_power = 0

    @override
    def fire_configuration_change(self) -> None:
        self.tec.fire_configuration_change()


def save_as(parent, file_type, file_extension, name) -> str:
    file_path = QtWidgets.QFileDialog.getSaveFileName(parent, caption=f"{name} Path",
                                                      filter=f"{file_type} (*.{file_extension});; All Files (*);;")[0]
    if file_path:
        _, old_file_extension = os.path.splitext(file_path)
        if not old_file_extension:
            file_path = file_path + "." + file_extension
        if os.path.exists(file_path):
            answer = QtWidgets.QMessageBox.question(parent, f"{name} Path",
                                                    f"File {file_path} exists already. Do you want to replace it?",
                                                    QtWidgets.QMessageBox.StandardButton.Yes
                                                    | QtWidgets.QMessageBox.StandardButton.No)
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                logging.warning("Overriding %s", file_path)
            else:
                file_path = ""
            if file_path:
                logging.info("Saved %s into %s", name, file_path)
    return file_path
