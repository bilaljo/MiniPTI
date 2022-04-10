#include "readCSV.h"
#include "pti.h"
#include "config.h"

int main() {
  parser::Config ptiConfig("pti.conf");
  parser::CSVFile data(std::get<std::string>(ptiConfig["Filepath"]["PTI_Inversion"]),
               std::get<char>(ptiConfig["Filepath"]["Delimiter"]));
  PTI pti(ptiConfig);
  pti.scaleSignals();
  pti.calculateInterferomticPhase();
  pti.calculatePTISignal();
  return 0;
}
