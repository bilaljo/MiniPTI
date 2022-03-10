#ifndef READ_BINARY_H
#define READ_BINARY_H

#include <stdio.h>

#define SAMPLES 50000

struct raw_data {
  double dc_1[SAMPLES];
  double dc_2[SAMPLES];
  double dc_3[SAMPLES];
  double reference[SAMPLES];
  double ac_1[SAMPLES];
  double ac_2[SAMPLES];
  double ac_3[SAMPLES];
};

FILE *open_file(const char *file_name);

void get_measurement(struct raw_data *raw_data, FILE *file);

#endif  /* READ_BINARY_H */
