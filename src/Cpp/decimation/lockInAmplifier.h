#pragma once
#include "readBinary.h"
#include <tuple>
#include <array>

namespace decimation {
  const int channels = 3;

  const int amplification = 1000;

  struct acData {
    std::array<double, channels> qudratur;
    std::array<double, channels> in_phase;
  };

  void generateReferences(const decimation::rawData& data, std::vector<double> &inPhase, std::vector<double> &quadratur);

  acData lockInFilter(const decimation::rawData& rawData, std::vector<double> &inPhase, std::vector<double> &quadratur);
}
