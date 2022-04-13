#include "OutputPhase.h"
#include <variant>
#include <cmath>
#ifdef _WIN32
  #include "..\parser\Config.h"
  #include "..\parser\CSV.h"
#else
  #include "../parser/Config.h"
  #include "../parser/CSV.h"
#endif

int main() {
  OutputPhase outputPhases;
  parser::Config ptiConfig("pti.conf");
  ptiConfig.openConfigFile();
  parser::CSVFile csvFile(std::get<std::string>(ptiConfig["file"]["phase_scan_path"]), std::get<char>(ptiConfig["file"]["delimiter"]));
  csvFile.readFile();
  outputPhases.setSignal({csvFile["DC1"], csvFile["DC2"], csvFile["DC3"]});
  outputPhases.scaleSignals();
  outputPhases.calculateBands(Detector_2);
  outputPhases.calculateBands(Detector_3);
  outputPhases.setBandRange();
  double outputPhase_1 = outputPhases.calculateOutputPhases(Detector_2);
  double outputPhase_2 = outputPhases.calculateOutputPhases(Detector_3);
  ptiConfig.addOption("output_phases", "detector_1", 0.0);
  if (outputPhase_1 > M_PI) {
    ptiConfig.addOption("output_phases", "detector_2", outputPhase_2);
    ptiConfig.addOption("output_phases", "detector_3", outputPhase_1);
  } else {
    ptiConfig.addOption("output_phases", "detector_2", outputPhase_1);
    ptiConfig.addOption("output_phases", "detector_3", outputPhase_2);
  }
  ptiConfig.addOption("output_phases", "phases_swapped", outputPhases.swappedPhases ? "true" : "false");
  ptiConfig.addOption("min_intensities", "detector_1", outputPhases.minIntensities[Detector_1]);
  ptiConfig.addOption("min_intensities", "detector_2", outputPhases.minIntensities[Detector_2]);
  ptiConfig.addOption("min_intensities", "detector_3", outputPhases.minIntensities[Detector_3]);
  ptiConfig.addOption("max_intensities", "detector_1", outputPhases.maxIntensities[Detector_1]);
  ptiConfig.addOption("max_intensities", "detector_2", outputPhases.maxIntensities[Detector_2]);
  ptiConfig.addOption("max_intensities", "detector_3", outputPhases.maxIntensities[Detector_3]);
  ptiConfig.writeConfig();
  return 0;
}
