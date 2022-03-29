#include "read_binary.h"
#include <stdio.h>
#include <string.h>

#define HEADER_SIZE 30
#define LABVIEW

void parse_command_line(int argc, char **argv, char *file_path, enum mode_t *mode) {
  if (argc > 1) {
    for (int i = 1; i < argc; i++) {
      if (! strcmp("file", argv[i])) {
        strcpy(file_path, argv[i + 1]);
      }
      if (! strcmp("binary", argv[i])) {
        *mode = BINARY;
      }
    }
  }
}

FILE *open_file(const char *file_path) {
  FILE *file = fopen(file_path, "rb");
  if (file == NULL) {
    perror("Error");
    return NULL;
  }
  /* We skip the header so the file pointer points directly to data. */
  char empty_string[HEADER_SIZE];
  fread(empty_string, sizeof(char), HEADER_SIZE, file);
  return file;
}

void get_measurement(struct raw_data *raw_data, FILE *file) {
  if (file == NULL) {
    perror("Error");
    return;  /* End of file reached. */
  }
  #ifdef LABVIEW
  int empty;
  fread(&empty, sizeof(int), 1, file);
  fread(&empty, sizeof(int), 1, file);
  #endif
  fread(raw_data->dc_1, sizeof(double), SAMPLES, file);
  fread(raw_data->dc_2, sizeof(double), SAMPLES, file);
  fread(raw_data->dc_3, sizeof(double), SAMPLES, file);
  fread(raw_data->reference, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_1, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_2, sizeof(double), SAMPLES, file);
  fread(raw_data->ac_3, sizeof(double), SAMPLES, file);
}
