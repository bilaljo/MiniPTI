#pragma once

#include <array>
#include <vector>
#include <unordered_map>
#include <map>
#include <string>
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

  std::map<std::string, std::vector<double>> getPTIData();

  static const int channels = 3;

  static const int phasesCombinations = 6;

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

  std::vector<std::array<double, channels>> _dcSignals = {};
  std::vector<std::array<AC, channels>> _acSignals = {};

  std::array<std::vector<double>, channels> _acPhases = {};
  std::array<std::vector<double>, channels> _acRValues = {};
  std::array<std::vector<double>, channels> _demoudlatedSignals = {};
};
