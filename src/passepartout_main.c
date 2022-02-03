#include <stddef.h>
#include <stdio.h>
#include <sys/time.h>
#include "read_csv.h"
#include "system_phases.h"

int main(void) {
  struct timeval  tv1, tv2;
  struct csv_file csv_file = {
    .names = {{0}},
    .data = {{0}},
  };
  struct intensity intentities[DATA_SIZE];
  size_t number_of_columns = get_names("../../dc.csv", csv_file.names);
  get_data("../../dc.csv", csv_file.data, number_of_columns);
  double system_phases[2] = {0};
  double intensity_dc_1[DATA_SIZE];
  double intensity_dc_2[DATA_SIZE];
  double intensity_dc_3[DATA_SIZE];
  for (int i = 0; i < DATA_SIZE; i++) {
    intensity_dc_1[i] = csv_file.data[i][DC_1];
    intensity_dc_2[i] = csv_file.data[i][DC_2];
    intensity_dc_3[i] = csv_file.data[i][DC_3];
  }
  set_intensities(&intensity_dc_1, &intensity_dc_2, &intensity_dc_3,
                  &intentities);
  gettimeofday(&tv1, NULL);
  get_phases(&system_phases, &intentities);
  gettimeofday(&tv2, NULL);
  printf ("Total time = %ld microseconds\n", (tv2.tv_usec - tv1.tv_usec) + (tv2.tv_sec - tv1.tv_sec));
  return 0;
}
