#include <fstream>
#include <variant>
#include "readBinary.h"
#ifdef _WIN32
#include "..\parser\Config.h"
  #include "..\parser\CSV.h"
#else
#include "../parser/Config.h"
#include "../parser/CSV.h"
#endif
#include "lockInAmplifier.h"

int main() {
  parser::Config config("pti.conf");
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
    decimation::acData ac = decimation::lockInFilter(rawData);
    decimation::dcSignal dc = decimation::calculate_dc(rawData);
  }
  return 0;
}
