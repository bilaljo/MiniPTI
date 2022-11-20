# Source Code, Algorithm and GUI for the MiniPTI

## **Version 1.0**
Version 1.0 provides the whole algorithms for offline evaluation, based on from LabView generated binary files.

### **Decimation**

It is good practice to use the decimation object with the with statement, so that the binary fill will automaticly closed.
Note that as the binary file iself can be very large (up to GB) the decimation will read the file chunckwise.
read_data reads a block of 50'000 samples of data and decode them into numpy arrays. The call of the decimation will than process the algorithms described in [1].
```python
import pandas as pd

import pti


binary_file = "data.bin"
output_data = defaultdict(list)
for channel in range(3):
    output_data[f"DC CH{i + 1}"] = "s"
    output_data[f"Lock In Amplitude CH{i + 1}"] = "V"
    output_data[f"Lock In Phase CH{i + 1}"] = "rad"
with pti.Decimation(binary_file) as decimation:
    while decimation.read_data():
        decimation()
        lock_in_amplitude, lock_in_phase = decimation.polar_lock_in()
    for channel in range(3):
        output_data[f"DC CH{i + 1}"] = self.dc_down_sampled[channel]
        output_data[f"Lock In Amplitude CH{i}"] = lock_in_amplitude[channel]
        output_data[f"Lock In Phase CH{i}"] = lock_in_phase[channel]
```

### **Interferometry**
The interferometry provides an API for calculating the interferometric phase and characterisising the interferometer (output phases, amplitudes and offsets). For a propper use it is needed to proive a configuration file. An example of such a file can be found in src/configs/settings.csv. There also settings files for other couplers and experiments.

**Calculating the interferometric Phase**
```python
from interferometry import interferometer


interferometer.settings_file_path = "configs/settings.csv"
interferometer.decimation_file_path = "data/Decimation.csv"
interferometer.calculate_offsets()  # Estimiate offsets
interferometer.calculate_amplitudes()  # Estimiate amplitudes
interferometer.calculate_phase()
```

**Characterising the Interferometer**
The characterisation uses interferometer object, as well the PTI Inversion. The accessed fields (output_phases, amplitudes and offsets) are threadsafe via locks.


### **PTI Inversion**
The pti inversion algorithms can be applied from a call to the functor or by calling the single function by itself. The first one is recommened if it is needed to run the whole procedure based on Decimation-Files. The second gives access to the actual API.

**Call over Functor**
```python
import pti


pti.Inversion().