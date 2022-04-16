#pragma once
#include "lockInAmplifier.h"

namespace decimation {
  struct dcSignal {
    double dc1;
    double dc2;
    double dc3;
  };

  dcSignal calculate_dc(decimation::rawData &rawData);

  void commonNoiseRejection(decimation::rawData &rawData, const decimation::dcSignal &dcSignal);
}
