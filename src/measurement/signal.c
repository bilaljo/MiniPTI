#include "signal.h"
#include <math.h>

void calculate_pti_signal(struct intensity_dc *dc_signal, struct intensity_ac *ac_signal, double *system_phases, size_t size) {
  for (int i = 0; i < size; i++) {
    delta_phi = []
    weight = [];
    for (size_t i = 0; i < size; i++) {
      double x = dc_signal->detector_1[i] + dc_signal->detector_2[i] * cos(system_phases[0]) + dc_signal->detector_3[i] * cos(system_phases[1]);
      double y = dc_signal->detector_1[i] + dc_signal->detector_2[i] * cos(system_phases[0]) + dc_signal->detector_3[i] * cos(system_phases[1]);
      double signal_phase = arctan2(y, x);
      double demodulated_signal =
    }
    signal_phase = np.arctan2(y, x);

    X = data[f
    "Norm D{j}X"][i]
    Y = data[f
    "Norm D{j}Y"][i]
    R = np.sqrt(X * *2 + Y * *2)
    theta = np.arctan2(Y, X)
    dms = R * np.cos(theta - system_phase[j - 1])
    phases.append(theta)
    delta_phi.append(dms / -np.sin(signal_phase - phi_d[j - 1]))
    weight.append(np.abs(-np.sin(signal_phase - phi_d[j - 1])))
    delta_phi = np.array(delta_phi)
    weight = np.array(weight)
    phi.append(np.abs(np.sum(delta_phi * weight) / np.sum(weight)))

  }}
