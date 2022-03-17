#include "read_binary.h"
#include <stdio.h>

#define HEADER_SIZE 30
#define SAMPLES 50000

FILE *open_file(const char *file_name) {
  FILE *data = fopen(file_name, "rb");
  if (! data) {
    perror("Error");
    return NULL;
  }
  /* We skip the header so the file pointer points directly to data. */
  char empty_string[HEADER_SIZE];
  // FIXME: Header makes strange thins
  fread(empty_string, sizeof(char), HEADER_SIZE, data);
  return data;
}

void get_measurement(struct raw_data *raw_data, FILE *file) {
  if (! file) {
    return;  /* End of file reached. */
  }
  double empty;
  fread(&empty, sizeof(double), 1, file);
  fread(raw_data->dc_1, sizeof(double), SAMPLES, file);
  fread(raw_data->dc_2, sizeof(double), SAMPLES, file);
  fread(raw_data->dc_3, sizeof(double), SAMPLES, file);
  fread(raw_data->reference, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_1, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_2, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_3, sizeof(double), SAMPLES, file);
}
