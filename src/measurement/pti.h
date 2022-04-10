#pragma once

#include <array>
#include <vector>
#include "config.h"
#include "readCSV.h"

class PTI {
 public:
    struct AC {
    double inPhaseComponent;
    double qudraturComponent;
  };

  PTI(parser::Config& config, parser::CSVFile& data);

  ~PTI();
  void scaleSignals();

  void calculateInterferomticPhase();

  void calculatePTISignal();

  static const int channels = 3;

  std::vector<double> _ptiSignal;

 private:
  std::unordered_map<std::string, bool> _modes;

  std::vector<double> _interferometricPhase = {};

  bool _swappPhases = false;
  std::array<double, channels> _minIntensities = {};
  std::array<double, channels> _maxIntensities = {};
  std::array<double, channels> _outputPhases = {};
  std::array<double, channels> _systemPhases = {};

  enum Channel {
    detector1,
    detector2,
    detector3,
  };

  std::vector<std::array<double, 3>> _dcSignals = {};
  std::vector<std::array<AC, 3>> _acSignals = {};

  std::vector<std::array<double, 3>> _acPhases = {};
  std::vector<std::array<double, 3>> _acRValues = {};
  std::vector<std::array<AC, 3>> _demoudlatedSignals = {};
};
