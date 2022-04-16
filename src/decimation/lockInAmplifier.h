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

  lockIn generateReferences(const decimation::rawData& data);

  acData lockInFilter(const decimation::rawData& rawData);
}
