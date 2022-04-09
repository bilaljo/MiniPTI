#pragma once

#include <string>
#include <array>
#include <vector>

const int channels = 3;

enum detector_t {
  Detector_1,
  Detector_2,
  Detector_3,
};

class OutputPhase {
 public:
  OutputPhase();
  ~OutputPhase();

  void setSignal(const std::array<std::vector<double>, 3> &signals);

  void scaleSignals();

  void calculateBands(detector_t detector);

  double calculateOutputPhases(detector_t detector);

  std::array<double, channels> minIntensities = {};
  std::array<double, channels> maxIntensities = {};

 private:
  double _outputPhase = 0;

  std::vector<std::array<double, 3>> _signal;

  std::array<std::vector<double>, 2> _bands = {};
};
