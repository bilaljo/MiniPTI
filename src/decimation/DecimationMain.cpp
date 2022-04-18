#include <variant>
#include "readBinary.h"
#ifdef _WIN32
#include "..\parser\Config.h"
#else
#include "../parser/Config.h"
#endif
#include "CommonNoiseRecjection.h"
#include "lockInAmplifier.h"
#include <iostream>

int main() {
  parser::Config config("pti.conf");
  config.openConfigFile();
  bool onlineMeasurement = std::get<std::string>(config["mode"]["online"]) == "true";
  std::ofstream output;
  if (onlineMeasurement) {
    output.open("Decimation.csv", std::ios::app);
  } else {
    output.open("Decimation.csv");
  }
  output << "DC1,DC2,DC3,X1,Y1,X2,Y2,X3,Y3" << std::endl;
  std::ifstream binaryData(std::get<std::string>(config["file"]["decimation_path"]), std::ios::binary);
  char header[30];
  binaryData.read(header, 30);
  decimation::rawData rawData;
  rawData.dc1.resize(decimation::samples, 0);
  rawData.dc2.resize(decimation::samples, 0);
  rawData.dc3.resize(decimation::samples, 0);
  rawData.ref.resize(decimation::samples, 0);
  rawData.ac1.resize(decimation::samples, 0);
  rawData.ac2.resize(decimation::samples, 0);
  rawData.ac3.resize(decimation::samples, 0);
  std::vector<double> inPhase;
  std::vector<double> quadratur;
  inPhase.resize(decimation::samples, 0);
  quadratur.resize(decimation::samples, 0);
  while (true) {
    if (binaryData.peek() == EOF) {
      if (onlineMeasurement) {
       // Should be implemented with multi-threading.
      } else {
        break;
      }
    }
    decimation::readBinary(binaryData, rawData);
    decimation::dcSignal dc = decimation::calculate_dc(rawData);
    decimation::calculate_dc(rawData);
    decimation::acData ac = decimation::lockInFilter(rawData, inPhase, quadratur);
    output << dc.dc1 << "," << dc.dc2 << "," << dc.dc3 << ",";
    for (int channel = 0; channel < decimation::channels - 1; channel++) {
      output << ac.in_phase[channel] << ",";
      output << ac.qudratur[channel] << ",";
    }
    output << ac.in_phase[decimation::channels - 1] << ",";
    output << ac.qudratur[decimation::channels - 1] << std::endl;
  }
  return 0;
}
