#include "outputPhase.h"
#include <algorithm>
#include <cmath>
#include <tuple>
#include <unordered_map>

OutputPhase::OutputPhase() = default;

OutputPhase::~OutputPhase() = default;

void OutputPhase::setSignal(const std::array<std::vector<double>, 3> &signals) {
  for (int i = 0; i < signals[0].size(); i++) {
    _signal[i][Detector_1] = signals[Detector_1][i];
    _signal[i][Detector_2] = signals[Detector_2][i];
    _signal[i][Detector_3] = signals[Detector_3][i];
  }
}

void OutputPhase::scaleSignals() {
  for (auto& dc : _signal) {
    for (int i = 0; i < 3; i++) {
      dc[i] = (dc[i] - minIntensities[i]) / (maxIntensities[i] - minIntensities[i]);
    }
  }
}

void OutputPhase::calculateBands() {
  for (const auto& dc : _signal) {
    for (int i = 0; i < 2; i++) {
      for (int j = 0; j < 2; j++) {
        _bands[Detector_2 - 1].push_back(pow(-1, i) * acos(dc[Detector_1]) + pow(-1, j) * acos(dc[Detector_2]));
        _bands[Detector_3 - 1].push_back(pow(-1, i) * acos(dc[Detector_1]) + pow(-1, j) * acos(dc[Detector_3]));
      }
    }
  }
}

static std::unordered_map<double, size_t> calculateHistogram(const std::vector<double> &data) {
  std::unordered_map<double, size_t> bins;
  auto numberOfBins = static_cast<size_t>(sqrt(static_cast<double>(data.size())));
  double min = *std::min_element(data.begin(), data.end());
  double max = *std::max_element(data.begin(), data.end());
  // The histogram can be divied into n buckets: buckets = (max - min) / n * bin + min. Reordering results in
  // bin = n * (bucket - min) / (max - min). If it is no integer, we round it up.
  for (const auto& element : data) {
    double bucket = static_cast<int>(static_cast<double>(numberOfBins) * (element - min) / (max - min) - min);
    bins[bucket]++;
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
    }
  }
  return maxBucket;
}
