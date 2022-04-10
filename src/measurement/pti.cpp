#include "pti.h"
#include <cmath>
#include <vector>
#include <algorithm>
#include "config.h"

#define COMBINATIONS 6

PTI::PTI(const parser::Config &ptiConfig) {
  for (int channel = 0; channel < channels; channel++) {
    _minIntensities[channel] = std::get<double>(ptiConfig["Min_Values"]["Detector_" + std::to_string(channel + 1)]);
    _maxIntensities[channel] = std::get<double>(ptiConfig["Max_Values"]["Detector_" + std::to_string(channel + 1)]);
    _outputPhases[channel] = std::get<double>(ptiConfig["Output_Phases"]["Detector_" + std::to_string(channel + 1)]);
    _systemPhases[channel] = std::get<double>(ptiConfig["System_Phases"]["Detector_" + std::to_string(channel + 1)]);
  }
  _swappPhases = std::get<char>(ptiConfig["System_Phases"]["Phases_Swapped"]) == '1' ? true : false;
  for (size_t i = 0; i < dcSignals[0].size(); i++) {
    _dcSignals.push_back({dcSignals[detector1][i], dcSignals[detector2][i], dcSignals[detector3][i]});
    _acSignals.push_back({acSignals[detector1][i], acSignals[detector2][i], acSignals[detector3][i]});
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
  for (const auto& dc : _dcSignals) {
    for (int i = 0; i < 3; i++) {
      x[i] = dc[i] * cos(_outputPhases[i]) + sqrt(1 - pow(dc[i], 2)) * sin(_outputPhases[i]);
      y[i] = dc[i] * sin(_outputPhases[i]) + sqrt(1 - pow(dc[i], 2)) * cos(_outputPhases[i]);
    }
  }
  for (const auto& dc : _dcSignals) {
    for (int i = 3; i < COMBINATIONS; i++) {
      x[i] = dc[i] * cos(_outputPhases[i - 3]) - sqrt(1 - pow(dc[i], 2)) * sin(_outputPhases[i - 3]);
      y[i] = dc[i] * sin(_outputPhases[i - 3]) - sqrt(1 - pow(dc[i], 2)) * cos(_outputPhases[i - 3]);
    }
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
  _interferometricPhase =  atan2(y_value, x_value);
}

double PTI::calculatePTISignal() {
  double ptiSignal = 0;
  double weight = 0;
  for (int i = 0; i < _dcSignals[detector1].size(); i++) {
    for (int channel = 0; channel < channels; channel++) {
      int sign = sin(_interferometricPhase - _outputPhases[channel]) >= 0 ? 1 : -1;
      double R = pow(_acSignals[i][channel].inPhaseComponent, 2) + pow(_acSignals[i][channel].qudraturComponent, 2);
      double acPhase = atan2(_acSignals[i][channel].qudraturComponent, _acSignals[i][channel].inPhaseComponent);
      double demodulatedSignal = R * cos(acPhase - _systemPhases[channel]);
      ptiSignal += demodulatedSignal * sign;
      weight += (_maxIntensities[channel] - _minIntensities[channel]) /
                 2 * fabs(sin(_interferometricPhase - _outputPhases[channel]));
    }
  }
  return ptiSignal / weight;
}
