#include "../../unity/unity.h"
#include <stdlib.h>
#include <stdio.h>
#include "read_csv.h"
#include "system_phases.h"

void setUp(void) {}

void tearDown(void) {}

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

void test_sample_data_1_python(void) {
  double phases[2];
  double phases_python[2] = {1.9763368647187394, 4.066313398781279};
  calculate_phases("./dc_1.csv", phases);
  TEST_ASSERT_EQUAL_DOUBLE(phases[0], phases_python[0]);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_sample_data_1_python);
  UNITY_END();
}
