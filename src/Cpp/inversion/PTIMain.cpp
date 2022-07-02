#include <variant>
#include <string>
#include <vector>
#include <map>
#include "Inversion.h"

int main() {
  parser::Config ptiConfig("../../pti.conf");
  ptiConfig.openConfigFile();
  parser::CSV data(std::get<std::string>(ptiConfig["file_path"]["pti_inversion"]));
  //data.findDelimter();
  data.setDelimiter(',');
  data.readFile();
  pti_inversion::Inversion pti(ptiConfig, data);
  pti.scaleSignals();
  pti.calculateInterferomticPhase();
  pti.calculatePTISignal();
  std::map<std::string, std::vector<double>> ptiData = pti.getPTIData();
  parser::CSV outputData("PTI_Inversion.csv");
  outputData.setDelimiter(data.getDelimiter());
  outputData.saveData(ptiData);
  return 0;
}
