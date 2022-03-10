#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include "read_binary.h"
#include "lock_in_amplifier.h"

#define BUFFER_SIZE 64
#define DATA_SIZE 2000

int main(int argc, char **argv) {
  char file_path[BUFFER_SIZE] = "220224_NO2.bin";
  struct timeval start, end;
  if (argc > 1) {
    strcpy(file_path, argv[1]);
  }
  gettimeofday(&start, NULL);
  FILE *binary_file = open_file(file_path);
  struct raw_data raw_data;
  struct raw_data refused_data;
  struct filtered_data filtered_data[DATA_SIZE];
  double sine_reference[SAMPLES];
  double cosine_reference[SAMPLES];
  get_measurement(&refused_data, binary_file);
  for (size_t second; second < DATA_SIZE; second++) {
    get_measurement(&raw_data, binary_file);
    generate_references(&raw_data, sine_reference, cosine_reference);
    filter_signals(&raw_data, &filtered_data[second], sine_reference, cosine_reference);
  }
  gettimeofday(&end, NULL);
  double time_taken = end.tv_sec + end.tv_usec / 1e6 -
                      start.tv_sec - start.tv_usec / 1e6; // in seconds
printf("time program took %f seconds to execute\n", time_taken);
  FILE *sine = fopen("sine.txt", "w");
  for (size_t second; second < SAMPLES; second++) {
    fprintf(sine, "%1.10f, ", sine_reference[second]);
  }
  FILE *results = fopen("data.csv", "w");
  fprintf(results, "AC X1, AC Y1, AC X2, AC Y2, AC X3, AC Y3\n");
  for (size_t second; second < DATA_SIZE; second++) {
    fprintf(results, "%1.10f,%1.10f,%1.10f,%1.10f,%1.10f,%1.10f\n", filtered_data[second].ac_1_X, filtered_data[second].ac_1_Y,
            filtered_data[second].ac_2_X, filtered_data[second].ac_2_Y, filtered_data[second].ac_3_X, filtered_data[second].ac_3_Y);
  }
  return 0;
}
