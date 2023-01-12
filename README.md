# MiniPTI

<p align="center">
<img alt="flowchart" src="https://www.fhnw.ch/de/medien/logos/media/fhnw_e_10mm.jpg" class="center">
</p>

In this library the python implementation of the algorithm from
[Waveguide based passively demodulated photothermal interferometer for light absorption measurements of trace substances](https://doi.org/10.1364/AO.476868)
is provided.

### Installation
```bash
pip install minipti
```
https://pypi.org/project/minipti/1.0/

The library can be split into sub-libraries:

#### 1. Interferometry

The Interferometry library provides algorithms to characterise a 3x3 coupler interferometer (calculating the output
phases,
amplitudes and offsets of the output DC-signals) for any given, measured DC-signals.
It also contains an API for calculating the current phase of the interferometer for given DC signals.

Note that this library is primarily designed for 3x3 couplers, but it can be easily extended for every amount of
outputs.

#### 2. PTI

PTI, short for Photo Thermal Inversion, provided the PTI-related algorithm from the mentioned paper above.
They include an algorithm for common mode noise rejection of high-resolution AC signals, decimation
and the actual PTI inversion.

Note that both sub-libraries provide only offline routines. Future versions will be provided
as well routines for live data.

A basic structure of the libraries with their classes is shown in the picture above
from the mentioned paper.

The picture below shows the basic file structure and the public members of the classes.

<p align="center">
<img alt="flowchart" src="https://raw.githubusercontent.com/bilaljo/MiniPTI/0dad7516c4a8105e1fcbecc22dcb905d3a4bee11/images/flowchart.svg" class="center">
</p>

## **Decimation**

The measured data for decimation is in binary file format generated from LabView.
It is good practice to use the decimation object with the ```with``` statement so that the binary fill will
automatically
be closed. Note that as the binary file itself can be very large (up to GB) the decimation will read the file
chunk-wise.
read_data reads a block of 50'000 samples of data and decodes them into NumPy arrays. The call of the decimation will
then process the algorithms described in [1].

```python
from collections import defaultdict

import pandas as pd
import minipti

binary_file = "data.bin"
output_data = defaultdict(list)
for i in range(3):
    output_data[f"DC CH{i + 1}"].append("s")
    output_data[f"Lock In Amplitude CH{i + 1}"].append("V")
    output_data[f"Lock In Phase CH{i + 1}"].append("rad")
with minipti.pti.Decimation(binary_file) as decimation:
    while decimation.read_data():
        decimation()
        for i in range(3):
            output_data[f"DC CH{i + 1}"].append(decimation.dc_down_sampled[i])
            output_data[f"Lock In Amplitude CH{i}"].append(decimation.lock_in.amplitude[i])
            output_data[f"Lock In Phase CH{i}"].append(decimation.lock_in.phase[i])
pd.DataFrame(output_data).to_csv("Decimation.csv")
```

## **Interferometry**

The interferometry provides an API for calculating the interferometric phase and characterising the interferometer
(output phases, amplitudes and offsets). For proper use, it is needed to provide a configuration file. An example of
such a file can be found in src/configs/settings.csv. There are also settings files for other couplers and experiments.

### **Calculating the interferometric Phase**

```python
import minipti
import pandas as pd

interferometer = minipti.interferometry.Interferometer()

interferometer.settings_file_path = "configs/settings.csv"
interferometer.decimation_filepath = "data/Decimation_Commercial.csv"
interferometer.init_settings()
data = pd.read_csv("data/Decimation_Commercial.csv")

dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()

interferometer.calculate_offsets(dc_signals)  # Estimate offsets
interferometer.calculate_amplitudes(dc_signals)  # Estimate amplitudes
interferometer.calculate_phase(dc_signals)
```

### **Characterising the Interferometer**

The characterisation uses an interferometer object, as well as the PTI Inversion. The accessed fields (output_phases,
amplitudes and offsets) are threadsafe via locks. If no output phases, amplitudes or offsets are known, the field
```use_settings``` can be set to ```False```. In this case, the settings will ignore and the parameters will be found by
repeating of calculating the interferometric phase and parameters.

characterization itself saves the data directly to ```data/Characterization.csv```
if you use the provided wrappers.

```python
import minipti

interferometer = minipti.interferometry.Interferometer()
interferometer.settings_file_path = "configs/settings.csv"
interferometer.decimation_filepath = "data/Decimation_Commercial.csv"
interferometer.init_settings()

characterization = minipti.interferometry.Characterization()
characterization(mode="offline")

characterization.use_settings = False
characterization(mode="offline")
```

### **Direct usage of API**

```python
import minipti
import pandas as pd

interferometer = minipti.interferometry.Interferometer()
dc_signals = pd.read_csv("data/Decimation_Commercial.csv")
characterization = minipti.interferometry.Characterization()
interferometer.settings_path = "configs/settings.csv"
characterization.signals = dc_signals[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
interferometer.init_settings()

# Without knowing any parameter
characterization.use_settings = False
characterization.iterate_characterization(characterization.signals.T)

# With knowing the parameters and already calculated phases
phases = pd.read_csv("data/PTI_Inversion_Commercial.csv")
characterization.phases = phases["Interferometric Phase"]
characterization.characterise_interferometer()
```

### **PTI Inversion**

The PTI inversion algorithms can be applied from a call to the functor or by calling the single function by itself. The
first one is recommended if it is needed to run the whole procedure based on Decimation-Files. The second gives access
to the actual API.

```python
import minipti

interferometer = minipti.interferometry.Interferometer()
interferometer.decimation_filepath = "data/Decimation_Commercial.csv"
interferometer.settings_path = "configs/settings.csv"
interferometer.init_settings()
inversion = minipti.pti.Inversion(interferometer=interferometer)
inversion(mode="offline")
```

### **Direct Usage of API**

```python
import pandas as pd
import minipti

interferometer = minipti.interferometry.Interferometer()
interferometer.decimation_filepath = "data/Decimation_Commercial.csv"
interferometer.settings_path = "configs/settings.csv"
interferometer.init_settings()
data = pd.read_csv("data/Decimation_Commercial.csv")

inversion = minipti.pti.Inversion(interferometer=interferometer)

dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
amplitudes = data[[f"Lock In Amplitude CH{i}" for i in range(1, 4)]].to_numpy().T
inversion.lock_in.amplitude = amplitudes
inversion.lock_in.phase = data[[f"Lock In Phase CH{i}" for i in range(1, 4)]].to_numpy().T

interferometer.calculate_phase(dc_signals)
inversion.calculate_sensitivity()
inversion.calculate_pti_signal()
```
