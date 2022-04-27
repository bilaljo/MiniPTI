#pragma once

#include <vector>
#include <string>
#include <fstream>
#ifdef _WIN32
#include "..\parser\Config.h"
#else
#include "../parser/Config.h"
#endif

namespace decimation {
  const int samples = 50000;

  struct rawData {
    std::vector<double> dc1;
    std::vector<double> dc2;
    std::vector<double> dc3;
    std::vector<double> ref;
    std::vector<double> ac1;
    std::vector<double> ac2;
    std::vector<double> ac3;
  };

  std::ifstream openFile(std::string fileName, parser::Config& config);

  void readBinary(std::ifstream &binaryData, rawData& rawData);
}
