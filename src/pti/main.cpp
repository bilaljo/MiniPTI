#include "../parser/readCSV.h"
#include "Inversion.h"
#include "../parser/config.h"
#include <variant>
#include <string>
#include <vector>
#include <map>

int main() {
  parser::Config ptiConfig("pti.conf");
  ptiConfig.openConfigFile();
  parser::CSVFile data(std::get<std::string>(ptiConfig["file"]["pti_inversion_path"]), std::get<char>(ptiConfig["file"]["delimiter"]));
  data.readFile();
  PTI::Inversion pti(ptiConfig, data);
  pti.scaleSignals();
  pti.calculateInterferomticPhase();
  pti.calculatePTISignal();
  std::map<std::string, std::vector<double>> ptiData = pti.getPTIData();
  parser::CSVFile outputData("output.csv", std::get<char>(ptiConfig["file"]["delimiter"]));
  outputData.saveData(ptiData);
  return 0;
}
