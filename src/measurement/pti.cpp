#include "pti.h"
#include <cmath>
#include <sstream>
#include <algorithm>
#include "config.h"
#include "readCSV.h"

#define COMBINATIONS 6

PTI::PTI(parser::Config& ptiConfig, parser::CSVFile& data) {
  for (int channel = 0; channel < channels; channel++) {
    _minIntensities[channel] = std::get<double>(ptiConfig["Min_Intensities"]["Detector_" + std::to_string(channel + 1)]);
    _maxIntensities[channel] = std::get<double>(ptiConfig["Max_Intensities"]["Detector_" + std::to_string(channel + 1)]);
    _outputPhases[channel] = std::get<double>(ptiConfig["Output_Phases"]["Detector_" + std::to_string(channel + 1)]);
    _systemPhases[channel] = std::get<double>(ptiConfig["System_Phases"]["Detector_" + std::to_string(channel + 1)]);
  }
  _modes["Online"] = std::get<std::string>(ptiConfig["Mode"]["Online"]) == "true" ? true : false;
  _modes["Offline"] = std::get<std::string>(ptiConfig["Mode"]["Offline"]) == "true" ? true : false;
  _modes["Verbose"] = std::get<std::string>(ptiConfig["Mode"]["Verbose"]) == "true" ? true : false;
  //std::istringstream()) >> std::boolalpha >> _swappPhases;
  _swappPhases = std::get<std::string>(ptiConfig["Output_Phases"]["Swapped_Phases"]) == "true" ? true : false;
  for (size_t i = 0; i < data.getSize(); i++) {
    std::array<double, channels> dc = {};
    std::array<AC, channels> ac = {};
    dc[detector1] = data["DC1"][i];
    ac[detector1].inPhaseComponent = data["X1"][i];
    ac[detector1].qudraturComponent = data["Y1"][i];
    if (_swappPhases) {
      dc[detector2] = data["DC3"][i];
      dc[detector3] = data["DC2"][i];
      ac[detector2].inPhaseComponent = data["X3"][i];
      ac[detector2].qudraturComponent = data["Y3"][i];
      ac[detector3].inPhaseComponent = data["X2"][i];
      ac[detector3].qudraturComponent = data["Y2"][i];
    } else {
      dc[detector2] = data["DC2"][i];
      dc[detector3] = data["DC3"][i];
      ac[detector2].inPhaseComponent = data["X2"][i];
      ac[detector2].qudraturComponent = data["Y2"][i];
      ac[detector3].inPhaseComponent = data["X3"][i];
      ac[detector3].qudraturComponent = data["Y3"][i];
    }
    _dcSignals.push_back(dc);
    _acSignals.push_back(ac);
  }
}

PTI::~PTI() = default;

void PTI::scaleSignals() {
  for (auto& dc : _dcSignals) {
    for (int i = 0; i < 3; i++) {
      dc[i] = 2 * (dc[i] - _minIntensities[i]) / (_maxIntensities[i] - _minIntensities[i]) - 1;
    }
  }
}
struct indices_t {
  int x[3];
  int y[3];
};

template<size_t size>
static double mean (std::array<double, size> data) {
  double currentMean = 0;
  for (const double& element : data) {
    currentMean += element;
  }
  return currentMean / static_cast<double>(data.size());
}

void PTI::calculateInterferomticPhase() {
  double x[COMBINATIONS] = {0};
  double y[COMBINATIONS] = {0};
  for (const auto &dc: _dcSignals) {
    for (int i = 0; i < 3; i++) {
      x[i] = dc[i] * cos(_outputPhases[i]) + sqrt(1 - pow(dc[i], 2)) * sin(_outputPhases[i]);
      y[i] = dc[i] * sin(_outputPhases[i]) + sqrt(1 - pow(dc[i], 2)) * cos(_outputPhases[i]);
    }
    for (int i = 3; i < COMBINATIONS; i++) {
      x[i] = dc[i] * cos(_outputPhases[i - 3]) - sqrt(1 - pow(dc[i], 2)) * sin(_outputPhases[i - 3]);
      y[i] = dc[i] * sin(_outputPhases[i - 3]) - sqrt(1 - pow(dc[i], 2)) * cos(_outputPhases[i - 3]);
    }
    double error_x = 6;
    double error_y = 6;
    double current_error_x = 6;
    double current_error_y = 6;
    struct indices_t indices = {};
    for (int i = 0; i < COMBINATIONS; i++) {
      for (int j = i + 1; j < COMBINATIONS; j++) {
        for (int k = j + 1; k < COMBINATIONS; k++) {
          error_x = fabs(x[i] - x[k]) + fabs(x[j] - x[i]) + fabs(x[j] - x[k]);
          error_y = fabs(y[i] - y[k]) + fabs(y[j] - y[i]) + fabs(y[j] - y[k]);
          if (current_error_x > error_x) {
            indices.x[0] = i;
            indices.x[1] = j;
            indices.x[2] = k;
          }
          if (current_error_y > error_y) {
            indices.y[0] = i;
            indices.y[1] = j;
            indices.y[2] = k;
          }
        }
      }
    }
    std::array<double, 3> xResults = {};
    std::array<double, 3> yResults = {};
    for (int i = 0; i < 3; i++) {
      xResults[i] = x[indices.x[i]];
      yResults[i] = y[indices.y[i]];
    }
    double x_value = mean<3>(xResults);
    double y_value = mean<3>(yResults);
    _interferometricPhase.push_back(atan2(y_value, x_value));
  }
}

void PTI::calculatePTISignal() {
  double ptiSignal = 0;
  double weight = 0;
  if (_modes["Verbose"]) {
    _acRValues.resize(_dcSignals.size());
    _acPhases.resize(_dcSignals.size());
  }
  std::fill(_acRValues.begin(), _acRValues.end(), 0);
  for (size_t i = 0; i < _dcSignals.size(); i++) {
    for (int channel = 0; channel < channels; channel++) {
      int sign = sin(_interferometricPhase[i] - _outputPhases[channel]) >= 0 ? 1 : -1;
      double R = sqrt(pow(_acSignals[i][channel].inPhaseComponent, 2) + pow(_acSignals[i][channel].qudraturComponent, 2));
      double acPhase = atan2(_acSignals[i][channel].qudraturComponent, _acSignals[i][channel].inPhaseComponent);
      double demodulatedSignal = R * cos(acPhase - _systemPhases[channel]);
      ptiSignal += demodulatedSignal * sign;
      weight += (_maxIntensities[channel] - _minIntensities[channel]) / 2 * fabs(sin(_interferometricPhase[i] - _outputPhases[channel]));
      if (_modes["Verbose"]) {
        _acRValues[i][channel] = R;
        _acPhases[i][channel] = acPhase;
      }
    }
    _ptiSignal.push_back(-ptiSignal / weight);
  }
}
