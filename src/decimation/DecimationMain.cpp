#include <unordered_map>
#include <variant>
#include "readBinary.h"
#ifdef _WIN32
#include "..\parser\Config.h"
#else
#include "../parser/Config.h"
#endif
#include "CommonNoiseRecjection.h"
#include "lockInAmplifier.h"

int main() {
  parser::Config config("pti.conf");
  std::ofstream output("decimation.csv", std::ios::app);
  output << "DC1,DC2,DC3,X1,Y1,X2,Y2,X3,Y3\n";
  std::ifstream binaryData(std::get<std::string>(config["file"]["decimation_path"]));
  decimation::rawData rawData = {};
  bool onlineMeasurement = std::get<std::string>(config["mode"]["online"]) == "true";
  while (true) {
    if (binaryData.peek() == EOF) {
      if (onlineMeasurement) {
       // Should be implemented with multi-threading.
      } else {
        break;
      }
    }
    rawData = decimation::readBinary(binaryData);
    decimation::dcSignal dc = decimation::calculate_dc(rawData);
    decimation::calculate_dc(rawData);
    decimation::acData ac = decimation::lockInFilter(rawData);
    output << dc.dc1 << "," << dc.dc2 << "," << dc.dc3 << ",";
    for (int channel = 0; channel < decimation::channels; channel++) {
      output << ac.in_phase[channel] << ",";
      output << ac.qudratur[channel] << ",";
    }
    output << "\n";
  }
  return 0;
}
