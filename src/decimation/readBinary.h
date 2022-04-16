#pragma once

#include <array>
#include <string>
#include <fstream>

namespace decimation {
  const int samples = 50000;

  const int signals = 6;

  struct rawData {
    std::array<double, samples> dc1;
    std::array<double, samples> dc2;
    std::array<double, samples> dc3;
    std::array<double, samples> ref;
    std::array<double, samples> ac1;
    std::array<double, samples> ac2;
    std::array<double, samples> ac3;
  };

  rawData readBinary(std::ifstream &binaryData);
}
