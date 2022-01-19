#include <stddef.h>
#include <stdio.h>
#include <math.h>
#include "read_csv.h"
#include "system_phases.h"
#define M_PI 3.14159265358979323846
int main(void) {
  struct csv_file csv_file = {
    .names = {{0}},
    .data = {{0}},
  };
  struct intensity intentities[DATA_SIZE];
  size_t number_of_columns = get_names("../data.csv", csv_file.names);
  /*for (int i = 0; i < number_of_columns - 1; i++) {
    printf("%s,", csv_file.names[i]);
  }
  printf("%s", csv_file.names[number_of_columns - 1]);*/
  get_data("../data.csv", csv_file.data, number_of_columns);
  /*for (size_t i = 0; i < NUMBER_OF_COLUMNS; i++) {
    for (size_t j = 0; j < number_of_columns; j++) {
      printf("%e,", csv_file.data[i][j]);
    }
    printf("%e\n", csv_file.data[i][number_of_columns - 1]);
  } */
  double system_phases[2] = {0};
  double intensity_dc_1[DATA_SIZE];
  double intensity_dc_2[DATA_SIZE];
  double intensity_dc_3[DATA_SIZE];
  for (int i = 0; i < DATA_SIZE; i++) {
    intensity_dc_1[i] = csv_file.data[i][DC_1];
    intensity_dc_2[i] = csv_file.data[i][DC_2];
    intensity_dc_3[i] = csv_file.data[i][DC_3];
  }
  /*for (int i = 0; i < DATA_SIZE; i++) {
    printf("%e\n", intensity_dc_1[i]);
  }*/
  set_intensities(&intensity_dc_1, &intensity_dc_2, &intensity_dc_3,
                  &intentities);
  get_phases(&system_phases, &intentities);
  printf("%1.10f, %1.10f", system_phases[0] / M_PI * 180, system_phases[1] / M_PI * 180);
  return 0;
}
