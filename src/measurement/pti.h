#pragma once

#include <array>
#include <vector>
#include "config.h"

class PTI {
 public:
    struct AC {
    double inPhaseComponent;
    double qudraturComponent;
  };

  PTI(const parser::Config &config);

  ~PTI();
  void scaleSignals();

  void calculateInterferomticPhase();

  double calculatePTISignal();

  static const int channels = 3;

  bool _swappPhases;

 private:
  double _interferometricPhase;
  std::array<double, channels> _minIntensities = {};
  std::array<double, channels> _maxIntensities = {};
  std::array<double, channels> _outputPhases = {};
  std::array<double, channels> _systemPhases = {};

  enum Channel {
    detector1,
    detector2,
    detector3,
  };

  std::vector<std::array<double, 3>> _dcSignals;
  std::vector<std::array<AC, 3>> _acSignals;
};
