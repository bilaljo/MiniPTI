#include "lockInAmplifier.h"
#include "readBinary.h"
#include <iostream>
#include <cmath>

void decimation::generateReferences(const decimation::rawData& data, std::vector<double> &inPhase, std::vector<double> &quadratur) {
  double period = 0;
  int signals = 0;
  int last_time = 0;
  int phase_shift = 0;
  bool first_run = true;
  /* Since the clock can slightly jitter we have to calculate the middle perioid of our signal. */
  for (int sample = 0; sample < decimation::samples - 1; sample++) {
    /* If we arive a rising edge we have change from low (below 1 / 10) to high (over 9 / 10).
     * The period is know the difference between the last seen tranisition and the current time.
    */
      if (data.ref[sample + 1] < 1.0 / 10 && data.ref[sample] > 9.0 / 10) {
        last_time = sample;
        if (first_run) {
          phase_shift = sample;
          first_run = false;
        }
      } else if (data.ref[sample] < 1.0 / 10 && data.ref[sample + 1] > 9.0 / 10
                 && sample > phase_shift) {
        period += 2.0 * (sample - last_time);
        signals++;
      }
    }
    if (! signals) {
      std::cerr << "No Modulation has occured" << std::endl;
      //exit(1);
    }
  period /= static_cast<double>(signals);
  for (int sample = 0; sample < decimation::samples; sample++) {
    inPhase[sample] = sin(2 * M_PI / period  * static_cast<double>(sample - phase_shift));
    quadratur[sample] = cos(2 * M_PI / period * static_cast<double>(sample - phase_shift));
  }
}

decimation::acData decimation::lockInFilter(const decimation::rawData& rawData, std::vector<double> &inPhase, std::vector<double> &quadratur) {
  acData ac = {};
  generateReferences(rawData, inPhase, quadratur);
  for (int sample = 0; sample < decimation::samples; sample++) {
    ac.in_phase[0] += rawData.ac1[sample] * inPhase[sample];
    ac.qudratur[0] += rawData.ac1[sample] * quadratur[sample];
    ac.in_phase[1] += rawData.ac2[sample] * inPhase[sample];
    ac.qudratur[1] += rawData.ac2[sample] * quadratur[sample];
    ac.in_phase[2] += rawData.ac3[sample] * inPhase[sample];
    ac.qudratur[2] += rawData.ac3[sample] * quadratur[sample];
  }
  ac.in_phase[0] /= (decimation::samples * decimation::amplification) ;
  ac.qudratur[0] /= (decimation::samples * decimation::amplification);
  ac.in_phase[1] /= (decimation::samples * decimation::amplification);
  ac.qudratur[1] /= (decimation::samples * decimation::amplification);
  ac.in_phase[2] /= (decimation::samples * decimation::amplification);
  ac.qudratur[2] /= (decimation::samples * decimation::amplification);
  return ac;
}
