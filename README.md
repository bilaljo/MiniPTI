# Installation
The libraries can be installed via the pip manager
## Interferometer
```bash
pip install interferometer
```

## PTI Inversion
```bash
pip install pti
```

# **Version 1.0**
Version 1.0 provides the whole algorithms for offline evaluation, based on from LabView generated binary files.

## **Decimation**

It is good practice to use the decimation object with the with statement, so that the binary fill will automatic
closed.  Note that as the binary file itself can be very large (up to GB) the decimation will read the file chunk wise.
read_data reads a block of 50'000 samples of data and decode them into numpy arrays. The call of the decimation will
than process the algorithms described in [1].
```python
from collections import defaultdict

import pandas as pd
import pti


binary_file = "data.bin"
output_data = defaultdict(list)
for i in range(3):
    output_data[f"DC CH{i + 1}"].append("s")
    output_data[f"Lock In Amplitude CH{i + 1}"].append("V")
    output_data[f"Lock In Phase CH{i + 1}"] .append("rad")
with pti.Decimation(binary_file) as decimation:
    while decimation.read_data():
        decimation()
        lock_in_amplitude, lock_in_phase = decimation.polar_lock_in()
    for i in range(3):
        output_data[f"DC CH{i + 1}"].append(decimation.dc_down_sampled[i])
        output_data[f"Lock In Amplitude CH{i}"].append(lock_in_amplitude[i])
        output_data[f"Lock In Phase CH{i}"].append(lock_in_phase[i])
pd.DataFrame(output_data).to_csv("Decimation.csv")
```

## **Interferometry**
The interferometry provides an API for calculating the interferometric phase and characterising the interferometer
(output phases, amplitudes and offsets). For a proper use it is needed to provide a configuration file. An example of
such a file can be found in src/configs/settings.csv. There also settings files for other couplers and experiments.

### **Calculating the interferometric Phase**

```python
from interferometry import interferometer


interferometer.settings_file_path = "configs/settings.csv"
interferometer.decimation_file_path = "data/Decimation.csv"
interferometer.calculate_offsets()  # Estimate offsets
interferometer.calculate_amplitudes()  # Estimate amplitudes
interferometer.calculate_phase()
```

### **Characterising the Interferometer**

The characterisation uses interferometer object, as well the PTI Inversion. The accessed fields (output_phases,
amplitudes and offsets) are threadsafe via locks. If no output phases, amplitudes or offsets are known, the field 
```use_settings``` can be set to ```False```. In this case the settings will ignore and the parameters will be found by
repeating of calculating the interferometric phase and parameters.

characterization itself saves the data directly to ```data/Characterization.csv```
if you use the provided wrappers.
```python
from interferometry import interferometer, Characterization
interferometer.settings_file_path = "configs/settings.csv"
interferometer.decimation_file_path = "data/Decimation.csv"

characterization = Characterization()
characterization(mode="offline")

characterization.use_settings = False
characterization(mode="offline")
```
### **Direct usage of API**
```python
from interferometry import interferometer, Characterization
import pandas as pd

dc_signals = pd.read_csv("Decimation.csv")
characterization = Characterization()
interferometer.settings_path = "configs/settings.csv"
characterization.signals = [dc_signals[f"DC CH{i}"] for i in range(1, 4)]

# Without knowing any parameter
characterization.use_settings = False
characterization.iterate_characterization()
print(characterization)

# With knowing the parameters and already calculated phases
phases = pd.read_csv("PTI_Inversion.csv")
characterization.phases = phases["Interferometric Phase"]
characterization.characterise_interferometer()
print(characterization)
```


### **PTI Inversion**
The pti inversion algorithms can be applied from a call to the functor or by calling the single function by itself. The
first one is recommended if it is needed to run the whole procedure based on Decimation-Files. The second gives access
to the actual API.

```python
import pandas as pd
import pti
from interferometry import interferometer


dc_signals = pd.read_csv("Decimation.csv")
interferometer.signals = [dc_signals[f"DC CH{i}"] for i in range(1, 4)]
inversion = pti.Inversion()
inversion(mode="offline")
```
### **Direct Usage of API**
```python
import pti
import pandas as pd
from interferometry import interferometer

dc_signals = pd.read_csv("Decimation.csv")
interferometer.signals = [dc_signals[f"DC CH{i}"] for i in range(1, 4)]
inversion = pti.Inversion()
interferometer.calculate_phase()

inversion.calculate_sensitivity()
inversion.calculate_pti_signal()
```
