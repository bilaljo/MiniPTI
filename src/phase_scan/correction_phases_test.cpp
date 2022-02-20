#include <gtest/gtest.h>
#include <math.h>
#include "read_csv.h"
#include "system_phases.h"

#define MAX_ERROR 1e-6

void calculate_phases(char *file_path, double *phases) {
  struct csv csv_file;
  read_csv(file_path, &csv_file);
  scale_signal(get_column(&csv_file, "Detector 1"));
  scale_signal(get_column(&csv_file, "Detector 2"));
  scale_signal(get_column(&csv_file, "Detector 3"));
  struct intensities intensities = {
    .detector_1 = get_column(&csv_file, "Detector 1"),
    .detector_2 = get_column(&csv_file, "Detector 2"),
    .detector_3 = get_column(&csv_file, "Detector 3"),
  };
  get_phases(phases, &intensities);
}

TEST(sample_data_1_python, Test) {
  double phases[2];
  double phases_python[2] = {1.9763368647187394, 4.066313398781279};
  calculate_phases((char*)"sample_data/dc_1.csv", phases);
  ASSERT_LE(fabs(phases_python[0] - phases[0]), MAX_ERROR);
}
