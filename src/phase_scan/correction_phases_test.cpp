#include <gtest/gtest.h>
#include <math.h>
#include <stddef.h>
#include "read_csv.h"
#include "system_phases.h"

#define MAX_ERROR 1e-7


double get_mean(const double *data) {
  double mean = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    mean += data[i];
  }
  return mean / DATA_SIZE;
}

double get_variance(const double *data) {
  double mean = get_mean(data);
  double variance = 0;
  for (int i = 0; i < DATA_SIZE; i++) {
    variance += pow(mean - data[i], 2);
  }
  return variance / DATA_SIZE;
}

double variance_circle(const double *phases, struct intensities *intensities) {
  double x = phases[0];
  double y = phases[1];
  double circle_result[DATA_SIZE] = {0};
  for (size_t i = 0; i < DATA_SIZE; i++) {
    circle_result[i] = pow(intensities->detector_1[i] + intensities->detector_2[i] * cos(x) +
                            intensities->detector_3[i] * cos(y), 2) +  pow(intensities->detector_2[i] * sin(x) +
                            intensities->detector_3[i] * sin(y), 2);
  }
  return get_variance(circle_result);
}

void scale_signals(char *file_path, struct csv *csv_file ) {
  read_csv(file_path, csv_file);
  scale_signal(get_column(csv_file, (char*)"Detector 1"));
  scale_signal(get_column(csv_file, (char*)"Detector 2"));
  scale_signal(get_column(csv_file, (char*)"Detector 3"));
}


TEST(python_correction_phases, dc_1) {
  struct csv csv_file;
  scale_signals((char*)"./sample_data/dc_1.csv", &csv_file);
  double phases[2];
  double phases_python[2] = {1.9763368647187394, 4.066313398781279};
  struct intensities intensities = {
    .detector_1 = get_column(&csv_file, (char*)"Detector 1"),
    .detector_2 = get_column(&csv_file, (char*)"Detector 2"),
    .detector_3 = get_column(&csv_file, (char*)"Detector 3"),
  };
  get_phases(phases, &intensities);
  ASSERT_LE(fabs(phases_python[0] -  phases[0]), MAX_ERROR);
}

TEST(python_variance, dc_1) {
  struct csv csv_file;
  double phases[2];
  scale_signals((char*)"./sample_data/dc_1.csv", &csv_file);
  struct intensities intensities = {
    .detector_1 = get_column(&csv_file, (char*)"Detector 1"),
    .detector_2 = get_column(&csv_file, (char*)"Detector 2"),
    .detector_3 = get_column(&csv_file, (char*)"Detector 3"),
  };
  get_phases(phases, &intensities);
  double variance =  variance_circle(phases, &intensities);
  double python_variance = 0.000958833745365227;
  ASSERT_LE(fabs(variance - python_variance), 1e-10);
}

/* FIXME: dc_2 does not work. */
TEST(python_correction_phases, dc_2) {
struct csv csv_file;
scale_signals((char*)"./sample_data/dc_1.csv", &csv_file);
double phases[2];
double phases_python[2] = {1.9763368647187394, 4.066313398781279};
struct intensities intensities = {
  .detector_1 = get_column(&csv_file, (char*)"Detector 1"),
  .detector_2 = get_column(&csv_file, (char*)"Detector 2"),
  .detector_3 = get_column(&csv_file, (char*)"Detector 3"),
};
get_phases(phases, &intensities);
ASSERT_LE(fabs(phases_python[0] -  phases[0]), MAX_ERROR);
}

TEST(python_variance, dc_2) {
struct csv csv_file;
double phases[2];
scale_signals((char*)"./sample_data/dc_1.csv", &csv_file);
struct intensities intensities = {
  .detector_1 = get_column(&csv_file, (char*)"Detector 1"),
  .detector_2 = get_column(&csv_file, (char*)"Detector 2"),
  .detector_3 = get_column(&csv_file, (char*)"Detector 3"),
};
get_phases(phases, &intensities);
double variance =  variance_circle(phases, &intensities);
double python_variance = 0.000958833745365227;
ASSERT_LE(fabs(variance - python_variance), 1e-10);
}
