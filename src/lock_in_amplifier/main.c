#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include "read_binary.h"
#include "lock_in_amplifier.h"

#define BUFFER_SIZE 64
#define DATA_SIZE 1700

int main(int argc, char **argv) {
  char file_path[BUFFER_SIZE] = "220224_NO2.bin";
  struct timeval start, end;
  if (argc > 1) {
    strcpy(file_path, argv[1]);
  }
  gettimeofday(&start, NULL);
  FILE *binary_file = open_file(file_path);
  if (binary_file == NULL) {
    perror("Error");
    return 1;
  }
  double sine_reference[SAMPLES] = {0};
  double cosine_reference[SAMPLES] = {0};
  FILE *results = fopen("data.csv", "w");
  if (results == NULL) {
    perror("Error");
    return 1;
  }
  struct raw_data raw_data = {0};
  fprintf(results, "i,X1,Y1,X2,Y2,X3,Y3,DC1,DC2,DC3\n");
  for (int second = 0; second < DATA_SIZE; second++) {
    struct filtered_data filtered_data = {0};
    struct dc_signal dc_signals = {0};
    get_measurement(&raw_data, binary_file);
    generate_references(&raw_data, sine_reference, cosine_reference);
    filter_signals(&raw_data, &filtered_data, sine_reference, cosine_reference);
    calculate_dc(&dc_signals, &raw_data);
    fprintf(results, "%d,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f\n", second,
            filtered_data.ac_1_X, filtered_data.ac_1_Y, filtered_data.ac_2_X, filtered_data.ac_2_Y,
            filtered_data.ac_3_X, filtered_data.ac_3_Y, dc_signals.DC_1, dc_signals.DC_2, dc_signals.DC_3);
  }
  gettimeofday(&end, NULL);
  double time_taken = (double)end.tv_sec + (double)end.tv_usec / 1e6
                      - (double)start.tv_sec -(double)start.tv_usec / 1e6;
  printf("Program took %f seconds to execute\n", time_taken);
  return 0;
}
