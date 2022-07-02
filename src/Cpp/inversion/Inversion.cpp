#include "Inversion.h"
#include <cmath>
#include <sstream>
#include <algorithm>
#include <numeric>

pti_inversion::Inversion::Inversion(parser::Config& ptiConfig, parser::CSV &data) {
  _minIntensities[0] = std::get<double>(ptiConfig["min_intensities"]["detector_1"]);
  _maxIntensities[0] = std::get<double>(ptiConfig["max_intensities"]["detector_1"]);
  for (int channel = 0; channel < channels; channel++) {
    try {
      _outputPhases[channel] = std::get<double>(ptiConfig["output_phases"]["detector_" + std::to_string(channel + 1)]);
      _systemPhases[channel] = std::get<double>(ptiConfig["system_phases"]["detector_" + std::to_string(channel + 1)]);
    } catch (const std::bad_variant_access&) {
      throw std::invalid_argument("Section or key-value pair does not exist.");
    }
  }
  try {
    _modes["online"] = std::get<std::string>(ptiConfig["mode"]["online"]) == "true";
    _modes["offline"] = std::get<std::string>(ptiConfig["mode"]["offline"]) == "true";
    _modes["verbose"] = std::get<std::string>(ptiConfig["mode"]["verbose"]) == "true";
    _swappPhases = std::get<std::string>(ptiConfig["output_phases"]["phases_swapped"]) == "true";
  } catch (const std::bad_variant_access&) {
    throw std::invalid_argument("Section or key-value pair does not exist.");
  }
  if (_swappPhases) {
    _minIntensities[1] = std::get<double>(ptiConfig["min_intensities"]["detector_3"]);
    _maxIntensities[1] = std::get<double>(ptiConfig["max_intensities"]["detector_2"]);
    _minIntensities[2] = std::get<double>(ptiConfig["min_intensities"]["detector_2"]);
    _maxIntensities[2] = std::get<double>(ptiConfig["max_intensities"]["detector_2"]);
  } else {
    _minIntensities[1] = std::get<double>(ptiConfig["min_intensities"]["detector_2"]);
    _maxIntensities[1] = std::get<double>(ptiConfig["max_intensities"]["detector_2"]);
    _minIntensities[2] = std::get<double>(ptiConfig["min_intensities"]["detector_3"]);
    _maxIntensities[2] = std::get<double>(ptiConfig["max_intensities"]["detector_3"]);
  }
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

pti_inversion::Inversion::~Inversion() = default;

void pti_inversion::Inversion::scaleSignals() {
  for (auto& dc : _dcSignals) {
    for (int channel = 0; channel < channels; channel++) {
      dc[channel] = 2 * (dc[channel] - _minIntensities[channel]) /
                        (_maxIntensities[channel] - _minIntensities[channel]) - 1;
    }
  }
}

void pti_inversion::Inversion::calculateInterferomticPhase() {;
  std::array<std::array<double, channels>, 2> x = {};
  std::array<std::array<double, channels>, 2> y = {};
  for (const auto& dc: _dcSignals) {
    for (int channel = 0; channel < channels; channel++) {
      x[channel][0] = dc[channel] * cos(_outputPhases[channel]) + sqrt(1 - pow(dc[channel], 2)) * sin(_outputPhases[channel]);
      x[channel][1] = dc[channel] * cos(_outputPhases[channel]) - sqrt(1 - pow(dc[channel], 2)) * sin(_outputPhases[channel]);
      y[channel][0] = dc[channel] * sin(_outputPhases[channel]) + sqrt(1 - pow(dc[channel], 2)) * cos(_outputPhases[channel]);
      y[channel][1] = dc[channel] * sin(_outputPhases[channel]) - sqrt(1 - pow(dc[channel], 2)) * cos(_outputPhases[channel]);
    }
    double error_x;
    double error_y;
    double current_error_x = std::numeric_limits<double>::infinity();
    double current_error_y = std::numeric_limits<double>::infinity();
    std::array<double, channels> xResult = {};
    std::array<double, channels> yResult = {};
    for (int i = 0; i < 2; i++) {
      for (int j = 0; j < 2; j++) {
        for (int k = 0; k < 2; k++) {
          error_x = fabs(x[0][i] - x[1][k]) + fabs(x[0][i] - x[2][j]) + fabs(x[1][k] - x[2][j]);
          error_y = fabs(y[0][i] - y[1][k]) + fabs(y[0][i] - y[2][j]) + fabs(y[1][k] - y[2][j]);
          if (current_error_x > error_x) {
            xResult[0] = x[0][i];
            xResult[1] = x[1][k];
            xResult[2] = x[2][j];
            current_error_x = error_x;
          }
          if (current_error_y > error_y) {
            yResult[0] = y[0][i];
            yResult[1] = y[1][k];
            yResult[2] = y[2][j];
            current_error_y = error_y;
          }
        }
      }
    }
    double x_value = std::accumulate(xResult.begin(), xResult.end(), 0.0) / channels;
    double y_value = std::accumulate(yResult.begin(), yResult.end(), 0.0) / channels;
    _interferometricPhase.push_back(atan2(y_value, x_value));
  }
}

void pti_inversion::Inversion::calculatePTISignal() {
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
        _demoudlatedSignals[channel].push_back(demodulatedSignal);
      }
    }
    _ptiSignal.push_back(-ptiSignal / weight);
  }
}

std::map<std::string, std::vector<double>> pti_inversion::Inversion::getPTIData() {
  std::map<std::string, std::vector<double>> outputData;
  outputData["PTI Signal"] = _ptiSignal;
  outputData["Interferometric Phase"] = _interferometricPhase;
  if (_modes["verbose"]) {
    for (int channel = 0; channel < channels; channel++) {
      outputData["Root Mean Square " + std::to_string(channel + 1)] = _acRValues[channel];
      outputData["Response Phase " + std::to_string(channel + 1)] = _acPhases[channel];
      outputData["Demodulated Signal " + std::to_string(channel + 1)] = _demoudlatedSignals[channel];
    }
  }
  return outputData;
}
