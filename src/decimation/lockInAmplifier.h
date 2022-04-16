#pragma once
#include "readBinary.h"
#include <tuple>

namespace decimation {
  typedef std::tuple<std::array<double, decimation::samples>, std::array<double, decimation::samples>> lockIn;

  const int channels = 3;

  const int amplification = 1000;

  struct acData {
    double qudratur[channels];
    double in_phase[channels];
  };

  struct dcSignal {
    double dc1;
    double dc2;
    double dc3;
  };

  acData lockInFilter(const decimation::rawData& rawData);

  lockIn generateReferences(const decimation::rawData& data);

  dcSignal calculate_dc(decimation::rawData &rawData);
}
