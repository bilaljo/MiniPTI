#include "OutputPhase.h"
#include <algorithm>
#include <cmath>
#include <tuple>
#include <unordered_map>
#include <ranges>

OutputPhase::OutputPhase() {
  swappedPhases = false;
}

OutputPhase::~OutputPhase() = default;

void OutputPhase::setSignal(const std::array<std::vector<double>, 3> &signals) {
  for (size_t i = 0; i < signals[0].size(); i++) {
    _signal.push_back({signals[Detector_1][i], signals[Detector_2][i], signals[Detector_3][i]});
  }
  for (int i = 0; i < 3; i++) {
    minIntensities[i] = *std::min_element(signals[i].begin(), signals[i].end() - 75000);
    maxIntensities[i] = *std::max_element(signals[i].begin(), signals[i].end() - 75000);
  }
}

void OutputPhase::scaleSignals() {
  for (auto& dc : _signal) {
    for (int i = 0; i < 3; i++) {
      dc[i] = 2 * (dc[i] - minIntensities[i]) / (maxIntensities[i] - minIntensities[i]) - 1;
    }
  }
}

void OutputPhase::calculateBands(detector_t detector) {
  for (auto dc = _signal.begin(); dc != _signal.begin() + 2000; dc++) {
    for (int i = 0; i < 2; i++) {
      for (int j = 0; j < 2; j++) {
        double phase = pow(-1, i) * acos((*dc)[Detector_1]) + pow(-1, j) * acos((*dc)[detector]);
        if (phase < 0) {
          _bands[detector - 1].push_back(phase + 2 * M_PI);
        } else {
          _bands[detector - 1].push_back(phase);
        }
      }
    }
  }
}

void OutputPhase::setBandRange() {
  size_t indexDetector2 = 0, indexDetector3 = 0;
  for (size_t i = 0; i < _signal.size(); i++) {
    if ((_signal[i][Detector_2] > 0 && _signal[i + 1][Detector_2] < 0) ||
        (_signal[i][Detector_2] < 0 && _signal[i + 1][Detector_2] > 0)) {
      indexDetector2 = i;
      break;
    }
  }
  for (size_t i = 0; i < _signal.size(); i++) {
      if ((_signal[i][Detector_3] > 0 && _signal[i + 1][Detector_3] < 0) ||
          (_signal[i][Detector_3] < 0 && _signal[i + 1][Detector_3] > 0)) {
      indexDetector3 = i;
      break;
    }
  }
  if (indexDetector2 < indexDetector3) {
    std::remove_if(_bands[Detector_2 - 1].begin(), _bands[Detector_2 - 1].end(),
                   [&](const auto &phase) { return phase <= M_PI; });
    std::remove_if(_bands[Detector_3 - 1].begin(), _bands[Detector_3 - 1].end(),
                   [&](const auto &phase) { return phase > M_PI; });
      swappedPhases = true;
  } else {
    std::remove_if(_bands[Detector_3 - 1].begin(), _bands[Detector_3 - 1].end(),
                   [&](const auto &phase) { return phase <= M_PI; });
    std::remove_if(_bands[Detector_2 - 1].begin(), _bands[Detector_2 - 1].end(),
                   [&](const auto &phase) { return phase > M_PI; });
  }
    /*
  = _bands[Detector_2] | std::views::filter([](double phase) {return phase > M_PI;});
  _bands[Detector_3 - 1] = _bands[Detector_3] | std::views::filter([](double phase) {return phase <= M_PI;});
} else {
  _bands[Detector_3 - 1] = _bands[Detector_3] | std::views::filter([](double phase) {return phase > M_PI;});
  _bands[Detector_2 - 1] = _bands[Detector_2] | std::views::filter([](double phase) {return phase <= M_PI;});*/
}


static std::unordered_map<double, size_t> calculateHistogram(const std::vector<double> &data) {
  std::unordered_map<double, size_t> bins;
  auto numberOfBins = static_cast<size_t>(sqrt(static_cast<double>(data.size())));
  double min = *std::min_element(data.begin(), data.end());
  double max = *std::max_element(data.begin(), data.end());
  std::vector<double> ranges;
  for (size_t i = 0; i < numberOfBins; i++) {
    double bin = min + (max - min) / static_cast<double>(numberOfBins) * static_cast<double>(i);
    ranges.push_back(bin);
  }
  std::sort(ranges.begin(), ranges.end());
  double bucket;
  for (const auto& element : data) {
    for (size_t i = 0; i < numberOfBins - 1; i++) {
      if (element >= ranges[i] && element < ranges[i + 1]) {
        bucket = ranges[i];
        bins[bucket]++;
        break;
      }
    }
  }
  return bins;
}

double OutputPhase::calculateOutputPhases(detector_t detector) {
  std::unordered_map<double, size_t> bins = calculateHistogram(_bands[detector - 1]);
  size_t currentMax = 0;
  double maxBucket = 0;
  for (const auto& [bucket, bin] : bins) {
    if (bin > currentMax) {
      maxBucket = bucket;
      currentMax = bin;
    }
  }
  return maxBucket;
}
