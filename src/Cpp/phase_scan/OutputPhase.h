#pragma once

#include <string>
#include <array>
#include <vector>
#include <ranges>

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

  void setBandRange();

  double calculateOutputPhases(detector_t detector);

  std::array<double, channels> minIntensities = {};
  std::array<double, channels> maxIntensities = {};

  bool swappedPhases;

 private:

  std::vector<std::array<double, 3>> _signal;

  std::array<std::vector<double>, 2> _bands = {};
};
