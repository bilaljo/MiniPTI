#include "readCSV.h"
#include "pti.h"
#include "config.h"
#include <variant>
#include <string>
#include <fstream>

int main() {
  parser::Config ptiConfig("pti.conf");
  ptiConfig.openConfigFile();
  parser::CSVFile data(std::get<std::string>(ptiConfig["File"]["PTI_Inversion_Path"]), std::get<char>(ptiConfig["File"]["Delimiter"]));
  data.readFile();
  PTI pti(ptiConfig, data);
  pti.scaleSignals();
  pti.calculateInterferomticPhase();
  pti.calculatePTISignal();
  //data.saveData();
  return 0;
}
