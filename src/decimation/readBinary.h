#pragma once

#include <vector>
#include <string>
#include <fstream>

namespace decimation {
  const int samples = 50;

  struct rawData {
    std::vector<double> dc1;
    std::vector<double> dc2;
    std::vector<double> dc3;
    std::vector<double> ref;
    std::vector<double> ac1;
    std::vector<double> ac2;
    std::vector<double> ac3;
  };

  void readBinary(std::ifstream &binaryData, rawData& rawData);
}
