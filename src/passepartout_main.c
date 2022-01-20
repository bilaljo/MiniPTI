#include <stddef.h>
#include <stdio.h>
#include <math.h>
#include <sys/time.h>
#include "read_csv.h"
#include "system_phases.h"

#define M_PI 3.14159265358979323846

int main(void) {
  struct timeval  tv1, tv2;
  struct csv_file csv_file = {
    .names = {{0}},
    .data = {{0}},
  };
  struct intensity intentities[DATA_SIZE];
  size_t number_of_columns = get_names("../data.csv", csv_file.names);
  get_data("../data.csv", csv_file.data, number_of_columns);
  double system_phases[2] = {0};
  double intensity_dc_1[DATA_SIZE];
  double intensity_dc_2[DATA_SIZE];
  double intensity_dc_3[DATA_SIZE];
  for (int i = 0; i < DATA_SIZE; i++) {
    intensity_dc_1[i] = csv_file.data[i][DC_1];
    intensity_dc_2[i] = csv_file.data[i][DC_2];
    intensity_dc_3[i] = csv_file.data[i][DC_3];
  }
  gettimeofday(&tv1, NULL);
  set_intensities(&intensity_dc_1, &intensity_dc_2, &intensity_dc_3,
                  &intentities);
  get_phases(&system_phases, &intentities);
  gettimeofday(&tv2, NULL);
  printf ("Total time = %f milliseconds\n",
          (double) (tv2.tv_usec - tv1.tv_usec) / 1000 +
          (double) (tv2.tv_sec - tv1.tv_sec));
  printf("%1.10f, %1.10f", system_phases[0] / M_PI * 180, system_phases[1] / M_PI * 180);
  return 0;
}
