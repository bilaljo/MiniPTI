#include <variant>
#include "outputPhase.h"
#include "config.h"
#include "readCSV.h"
#include <cmath>

int main() {
  OutputPhase outputPhases;
  parser::Config ptiConfig("pti.conf");
  ptiConfig.openConfigFile();
  parser::CSVFile csvFile(std::get<std::string>(ptiConfig["File"]["PTI_Inversion_Path"]), std::get<char>(ptiConfig["File"]["Delimiter"]));
  csvFile.readFile();
  outputPhases.setSignal({csvFile["DC1"], csvFile["DC2"], csvFile["DC3"]});
  outputPhases.scaleSignals();
  outputPhases.calculateBands(Detector_2);
  outputPhases.calculateBands(Detector_3);
  outputPhases.setBandRange();
  double outputPhase_1 = outputPhases.calculateOutputPhases(Detector_2);
  double outputPhase_2 = outputPhases.calculateOutputPhases(Detector_3);
  ptiConfig.addOption("Output_Phases", "Detector_1", 0.0);
  if (outputPhase_1 > M_PI) {
    ptiConfig.addOption("Output_Phases", "Detector_2", outputPhase_2);
    ptiConfig.addOption("Output_Phases", "Detector_3", outputPhase_1);
  } else {
    ptiConfig.addOption("Output_Phases", "Detector_2", outputPhase_1);
    ptiConfig.addOption("Output_Phases", "Detector_3", outputPhase_2);
  }
  ptiConfig.addOption("Output_Phases", "Phases_Swapped", outputPhases.swappedPhases ? "true" : "false");
  ptiConfig.addOption("Min_Intensities", "Detector_1", outputPhases.minIntensities[Detector_1]);
  ptiConfig.addOption("Min_Intensities", "Detector_2", outputPhases.minIntensities[Detector_2]);
  ptiConfig.addOption("Min_Intensities", "Detector_3", outputPhases.minIntensities[Detector_3]);
  ptiConfig.addOption("Max_Intensities", "Detector_1", outputPhases.maxIntensities[Detector_1]);
  ptiConfig.addOption("Max_Intensities", "Detector_2", outputPhases.maxIntensities[Detector_2]);
  ptiConfig.addOption("Max_Intensities", "Detector_3", outputPhases.maxIntensities[Detector_3]);
  ptiConfig.writeConfig();
  return 0;
}