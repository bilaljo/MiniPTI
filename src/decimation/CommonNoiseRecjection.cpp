#include "CommonNoiseRecjection.h"

decimation::dcSignal decimation::calculate_dc(decimation::rawData &rawData) {
  decimation::dcSignal dcSignal = {};
  for (int sample = 0; sample < decimation::samples; sample++) {
    dcSignal.dc1 += rawData.dc1[sample];
    dcSignal.dc2 += rawData.dc2[sample];
    dcSignal.dc3 += rawData.dc3[sample];
  }
  dcSignal.dc1 /= decimation::samples;
  dcSignal.dc2 /= decimation::samples;
  dcSignal.dc3 /= decimation::samples;
  return dcSignal;
}

void decimation::commonNoiseRejection(decimation::rawData &rawData, const decimation::dcSignal &dcSignal) {
  double totalDC = dcSignal.dc1 + dcSignal.dc2 + dcSignal.dc3;
  double noise;
  for (int sample = 0; sample < decimation::samples; sample++) {
    noise = rawData.ac1[sample] + rawData.ac2[sample] + rawData.ac3[sample];
    rawData.ac1[sample] = rawData.ac1[sample] - dcSignal.dc1 / totalDC * noise;
    rawData.ac2[sample] = rawData.ac2[sample] - dcSignal.dc2 / totalDC * noise;
    rawData.ac3[sample] = rawData.ac3[sample] - dcSignal.dc3 / totalDC * noise;
  }
}
