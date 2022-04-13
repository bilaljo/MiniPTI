#include "Inversion.h"
#include <cmath>
#include <sstream>
#include <algorithm>
#include <tuple>
#include "../parser/config.h"
#include "../parser/readCSV.h"

#define COMBINATIONS 6

PTI::Inversion::Inversion(parser::Config& ptiConfig, parser::CSVFile &data) {
  for (int channel = 0; channel < channels; channel++) {
    _minIntensities[channel] = std::get<double>(ptiConfig["min_intensities"]["detector_" + std::to_string(channel + 1)]);
    _maxIntensities[channel] = std::get<double>(ptiConfig["max_intensities"]["detector_" + std::to_string(channel + 1)]);
    _outputPhases[channel] = std::get<double>(ptiConfig["output_phases"]["detector_" + std::to_string(channel + 1)]);
    _systemPhases[channel] = std::get<double>(ptiConfig["system_phases"]["detector_" + std::to_string(channel + 1)]);
  }
  _modes["online"] = std::get<std::string>(ptiConfig["mode"]["online"]) == "true" ? true : false;
  _modes["offline"] = std::get<std::string>(ptiConfig["mode"]["offline"]) == "true" ? true : false;
  _modes["verbose"] = std::get<std::string>(ptiConfig["mode"]["verbose"]) == "true" ? true : false;
  //std::istringstream()) >> std::boolalpha >> _swappPhases;
  _swappPhases = std::get<std::string>(ptiConfig["output_phases"]["phases_swapped"]) == "true" ? true : false;
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

PTI::Inversion::~Inversion() = default;

void PTI::Inversion::scaleSignals() {
  for (auto& dc : _dcSignals) {
    for (int channel = 0; channel < channels; channel++) {
      dc[channel] = 2 * (dc[channel] - _minIntensities[channel]) / (_maxIntensities[channel] - _minIntensities[channel]) - 1;
    }
  }
}

template<size_t size>
static double mean (std::array<double, size> data) {
  double currentMean = 0;
  for (const double& element : data) {
    currentMean += element;
  }
  return currentMean / static_cast<double>(size);
}


void PTI::Inversion::calculateInterferomticPhase() {;
  std::array<double, phasesCombinations> x = {};
  std::array<double, phasesCombinations> y = {};
  for (const auto& dc: _dcSignals) {
    for (int channel = 0; channel < channels; channel++) {
      x[channel] = dc[channel] * cos(_outputPhases[channel]) + sqrt(1 - pow(dc[channel], 2)) * sin(_outputPhases[channel]);
      y[channel] = dc[channel] * sin(_outputPhases[channel]) + sqrt(1 - pow(dc[channel], 2)) * cos(_outputPhases[channel]);
      x[channel + channels] = dc[channel] * cos(_outputPhases[channel]) - sqrt(1 - pow(dc[channel], 2)) * sin(_outputPhases[channel]);
      y[channel + channels] = dc[channel] * sin(_outputPhases[channel]) - sqrt(1 - pow(dc[channel], 2)) * cos(_outputPhases[channel]);
    }
    double error_x;
    double error_y;
    double current_error_x = 6;
    double current_error_y = 6;
    std::array<size_t, channels> indicesX = {};
    std::array<size_t, channels> indicesY = {};
    for (int i = 0; i < COMBINATIONS; i++) {
      for (int j = i + 1; j < COMBINATIONS; j++) {
        for (int k = j + 1; k < COMBINATIONS; k++) {
          error_x = fabs(x[i] - x[k]) + fabs(x[j] - x[i]) + fabs(x[j] - x[k]);
          error_y = fabs(y[i] - y[k]) + fabs(y[j] - y[i]) + fabs(y[j] - y[k]);
          if (current_error_x > error_x) {
            indicesX[0] = i;
            indicesX[1] = j;
            indicesX[2] = k;
            current_error_x = error_x;
          }
          if (current_error_y > error_y) {
            indicesY[0] = i;
            indicesY[1] = j;
            indicesY[2] = k;
            current_error_y = error_y;
          }
        }
      }
    }
    std::array<double, 3> xResults = {};
    std::array<double, 3> yResults = {};
    for (int i = 0; i < 3; i++) {
      xResults[i] = x[indicesX[i]];
      yResults[i] = y[indicesY[i]];
    }
    double x_value = mean<3>(xResults);
    double y_value = mean<3>(yResults);
    _interferometricPhase.push_back(atan2(y_value, x_value));
  }
}

void PTI::Inversion::calculatePTISignal() {
  for (size_t i = 0; i < _dcSignals.size(); i++) {
    double ptiSignal = 0;
    double weight = 0;
    for (int channel = 0; channel < channels; channel++) {
      int sign = sin(_interferometricPhase[i] - _outputPhases[channel]) >= 0 ? 1 : -1;
      double R = sqrt(pow(_acSignals[i][channel].inPhaseComponent, 2) + pow(_acSignals[i][channel].qudraturComponent, 2));
      double acPhase = atan2(_acSignals[i][channel].qudraturComponent, _acSignals[i][channel].inPhaseComponent);
      double demodulatedSignal = R * cos(acPhase - _systemPhases[channel]);
      ptiSignal += demodulatedSignal * sign;
      weight += (_maxIntensities[channel] - _minIntensities[channel]) / 2 * fabs(sin(_interferometricPhase[i] - _outputPhases[channel]));
      if (_modes["verbose"]) {
        _acRValues[channel].push_back(R);
        _acPhases[channel].push_back(acPhase);
      }
    }
    _ptiSignal.push_back(-ptiSignal / weight);
  }
}

std::map<std::string, std::vector<double>> PTI::Inversion::getPTIData() {
  std::map<std::string, std::vector<double>> outputData;
  outputData["PTI"] = _ptiSignal;
  if (_modes["verbose"]) {
    outputData["Interferometric Phase"] = _interferometricPhase;
    for (int channel = 0; channel < channels; channel++) {
      outputData["R" + std::to_string(channel + 1)] = _acRValues[channel];
      outputData["System_Phase_" + std::to_string(channel + 1)] = _acPhases[channel];
    }
  }
  return outputData;
}
