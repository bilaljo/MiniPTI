#include "helper.h"
#include <vector>

void scaleDC(std::vector<double> data) {
  double minValue = *std::min(data.begin(), data.end());
  double maxValue = *std::max(data.begin(),data.end());
  for (double &element : data) {
    element = 2 * (element - minValue) / (maxValue - minValue) - 1;
  }
}
