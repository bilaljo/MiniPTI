#include <vector>
#include <iostream>
#include <cmath>
#include <algorithm>
#include <map>
#include "systemPhases.h"
#include "readCSV.h"
#include "helper.h"

int main() {
  CSVFile<double> data("../dc.csv");
  data.readFile();
  std::map<std::string, std::vector<double>> intensities;
  for (size_t i = 1; i < 4; i++) {
    phaseScan::scaleDC(data["Detector " + std::to_string(i)]);
  }
  phaseScan::SystemPhases<double> phases;
  std::array<double, 2> systemPhases = phases.getPhases();
  std::cout << systemPhases[0] << ", " << systemPhases[1] << std::endl;
  return 0;
}
