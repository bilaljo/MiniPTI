
# MiniPTI-GUI
<p style="text-align: center;">
<img alt="logo" src="https://www.fhnw.ch/de/medien/logos/media/fhnw_e_10mm.jpg" class="centre">
</p>


In this repository a GUI is provided to control the MiniPTI as also presented in [Waveguide based passively demodulated photothermal interferometer for light absorption measurements of trace substances](https://doi.org/10.1364/AO.476868). In addition to the GUI, Python implementations of the presented algorithms and the driver software for the MiniPTI hardware are also provided as libraries.

The library and GUI are tested for Ubuntu 22.04 LTS, Windows 10, Windows 11 and Raspberry Pi OS.

If hardware access is needed (i.e. serial ports) it works only on Windows and Unix.
# 1. installation
To install the library + GUI you can use the pip package manager. Just type in the console
```
pip install minipti
```

# 2. The GUI
The GUI is designed to be highly configurable. In minipti/gui/configs you will find
is a configs folder from which the desired functionality can be selected. Bloew
are shown some example configurations.

### 2.1 Interfereomtry GUI
In the interferometry GUI, only DC signals and interferometric phase are shown
in the home tab. While pressing "run" the probe laser (if existing) and motherboard are
running.

The GUI supports dark mode

<p style="text-align: center;">
<img alt="interferometry" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/interferometry/dark.png" class="centre">
</p>

and detect as well a theme detection of the OS to light theme.
<p style="text-align: center;">
<img alt="interferometry_light" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/interferometry/light.png" class="centre">
</p>


### 2.2 PTI GUI
In the PTI GUI (used for the Passepartout project), DC signals, interferometric phase and PTI Signal
are displayed only on the home tab. While pressing "run" the probe laser (if existing), pump laser and motherboard are
running.

<p style="text-align: center;">
<img alt="pti" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/pti/no2_example.png" class="centre">
</p>

### 2.3 Probe Laser GUI
It is possible to use the GUI to controll a custom build probe laser driver together with a custom build tec driver of the FHNW. An example
GUI is shown (configured such, that only Probe Laser relevant features are their) below.

**Laser Driver**
<p style="text-align: center;">
<img alt="probe_laser_driver" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/probe_laser/laser_driver.png" class="centre">
</p>

**Tec Driver**
<p style="text-align: center;">
<img alt="probe_tec_driver" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/probe_laser/tec_driver.png" class="centre">
</p>

### 2.4 Pump Laser GUI
It is also possible to use the GUI with the pump laser only if proberly configured. Note that the Pump Laser is moduldated with 80 Hz, but the transmitted
values of current are average on the driver.

<p style="text-align: center;">
<img alt="pump_tec_driver" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/develop/images/gui/pump_laser/laser_driver.png" class="centre">
</p>


# 3. Libraries

### 3.1 Algorithm
The subpackage Algorithm contains the implementation of the algorithms and can be divided into the subpackages interferometry and pti. interferometry contains the algorithms for the interferometric phase and characterisation of the interferometer. pti contains the algorithms for decimation and PTI inversion.

It is also possible to use only the interferometer subpackage without having to install dependencies for the other packages.

#### 3.1.1 Interferometry
interferometry contains the classes interferometer and characterisation.
Examples of usage can be found under <a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/interferometry.py">examples/interferometer.py</a> and
<a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/characterisation.py">examples/characterisation.py</a>.
### 3.1.2 PTI
pti contains the classes decimation inversion. Example calls can be found under <a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/pti_inversion.py">examples/pti_inversion.py</a>
### 3.2 Hardware
Hardware contains the classes to control the motherboard (DAQ + BMS), laser (Probe and Pump Laser) and TEC driver as well as the valve control.

# 4. Sources of Ressources
For the GUI some external public licence pictures were used which are listed below:

### 4.1 Gear Icon for Settings
https://freesvg.org/qubodup-cog-cogwheel-gear-zahnrad

### 4.2 Calculation Iccon
https://publicdomainvectors.org/en/free-clipart/Vector-clip-art-of-gray-computer-spreadsheet-document-icon/21207.html

### 4.3 Play Icon for run
https://freesvg.org/play-button

### 4.4 USB icon for connect
https://publicdomainvectors.org/en/free-clipart/International-symbol-for-USB-vector-clip-art/20833.html

### 4.5 Laser warning icon
https://publicdomainvectors.org/de/kostenlose-vektorgrafiken/Vektor-Bild-der-dreieckigen-Laser-Strahl-Warnschild/17874.html


### 4.6 Shutdown Icon
https://commons.wikimedia.org/wiki/File:Breathe-system-shutdown.svg

