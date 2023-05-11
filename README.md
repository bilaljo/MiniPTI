# MiniPTI

<p style="text-align: center;">
<img alt="flowchart" src="https://www.fhnw.ch/de/medien/logos/media/fhnw_e_10mm.jpg" class="centre">
</p>

In this repository a GUI is provided to control the MiniPTI as also presented in [Waveguide based passively demodulated photothermal interferometer for light absorption measurements of trace substances](https://doi.org/10.1364/AO.476868). In addition to the GUI, Python implementations of the presented algorithms and the driver software for the MiniPTI hardware are also provided as libraries.

# 1. installation
In order to make the library light-weighted different installation options exist.

To install only the interferometry library you can install it with
```
pip install minipti
```
To additionally use the inversion algorithm you can type
```bash
pip install minipti[algorithm]
```
To install the entire package (GUI, algorithms and hardware drivers) you can type
```bash
pip install minipti[gui]
```
# 2. Usage and GUI
The GUI can be used via
```bash
python -m minipti
```

## 2.1 Home Tab
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/home.png">
</p>

## 2.2 Pump Laser Tab
### 2.2.1 Pump Laser Driver Tab
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/pump_laser_tab.png">
</p>

### 2.2.2 Pump Laser Tec Driver Tab
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/pump_tec.png">
</p>

## 2.3 Probe Laser Tab
### 2.3.1 Probe Laser Driver Tab
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/probe_laser_tab.png">
</p>

### 2.3.1 Probe Laser Tec Driver Tab
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/probe_tec.png">
</p>

## 2.3 Plotting Tabs
### 2.3.1 DC Signals
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/dc_tab.png">
</p>

### 2.3.2 Amplitudes
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/amplitudes_tab.png">
</p>

### 2.3.3 Output Phases
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/output_phases_tab.png">
</p>

### 2.3.4 Interferometric Phase
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/phase_tab.png">
</p>

### 2.3.5 Sensitivity
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/sensitivity_tab.png">
</p>

### 2.3.6 Symmetry
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/sym_tab.png">
</p>

### 2.3.7 PTI Signal
<p style="text-align: center;">
<img alt="flowchart" src="images/gui/pti_signal_tab.png">
</p>

# 3. libraries

## 3.1 Algorithm
The subpackage Algorithm contains the implementation of the algorithms and can be divided into the subpackages interferometry and pti. interferometry contains the algorithms for the interferometric phase and characterisation of the interferometer. pti contains the algorithms for decimation and PTI inversion.

It is also possible to use only the interferometer subpackage without having to install dependencies for the other packages.

### 3.1.1 Interferometry
interferometry contains the classes interferometer and characterisation.
Examples of usage can be found under <a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/interferometry.py">examples/interferometer.py</a> and
<a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/characterisation.py">examples/characterisation.py</a>.
### 3.1.2 PTI
pti contains the classes decimation inversion. Example calls can be found under <a href="https://github.com/bilaljo/MiniPTI/blob/main/examples/pti_inversion.py">examples/pti_inversion.py</a>
## 3.2 Hardware
Hardware contains the classes to control the motherboard (DAQ + BMS), laser (Probe and Pump Laser) and TEC driver as well as the valve control.
