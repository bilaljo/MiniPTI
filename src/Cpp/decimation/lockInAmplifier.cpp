#include "lockInAmplifier.h"
#include "readBinary.h"
#include <cmath>

const int frequency = 80;
const double phaseShift = 0.00133;

void decimation::generateReferences(const decimation::rawData& data, std::vector<double> &inPhase,
                                    std::vector<double> &quadratur) {
  for (int sample = 0; sample < decimation::samples; sample++) {
    inPhase[sample] = sin(2 * M_PI * frequency  * (static_cast<double>(sample) / decimation::samples + phaseShift));
    quadratur[sample] = cos(2 * M_PI * frequency * (static_cast<double>(sample) / decimation::samples + phaseShift));
  }
}

decimation::acData decimation::lockInFilter(const decimation::rawData& rawData, std::vector<double> &inPhase, std::vector<double> &quadratur) {
  acData ac = {};
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
