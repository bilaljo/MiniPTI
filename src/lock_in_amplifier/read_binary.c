#include "read_binary.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define HEADER_SIZE 30
#define LABVIEW
#define SAMPLES 50000

enum mode mode = NORMAL;

void parse_command_line(int argc, char **argv, char *file_path) {
  if (argc > 1) {
    for (int i = 1; i < argc; i++) {
      if (! strcmp("file", argv[i])) {
        strcpy(file_path, argv[i + 1]);
      }
      if (! strcmp("debug", argv[i])) {
        mode = DEBUG;
      } else if (! strcmp("verbose", argv[i])) {
        mode = VERBOSE;
      }
    }
  }
}

FILE *open_file(const char *file_name) {
  FILE *data = fopen(file_name, "rb");
  if (data == NULL) {
    perror("Error");
    return NULL;
  }
  /* We skip the header so the file pointer points directly to data. */
  char empty_string[HEADER_SIZE];
  fread(empty_string, sizeof(char), HEADER_SIZE, data);
  return data;
}

void get_measurement(struct raw_data *raw_data, FILE *file) {
  if (file == NULL) {
    return;  /* End of file reached. */
  }
  int empty;
  switch (mode) {
    case DEBUG:
      #ifdef LABVIEW
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
      break;
    case ONLINE:
      /* TODO: Figure out if read instead of fread would more efficient here. */
      for (int i = 0; i < SAMPLES; i++) {
        fread(raw_data->dc_1, sizeof(double), 1, file);
        fread(raw_data->dc_2, sizeof(double), 1, file);
        fread(raw_data->dc_3, sizeof(double), 1, file);
        fread(raw_data->reference, sizeof(double), 1, file);
        fread(raw_data->ac_1, sizeof(double), 1, file);
        fread(raw_data->ac_2, sizeof(double), 1, file);
        fread(raw_data->ac_3, sizeof(double), 1, file);
        /* TODO: Does we really need a sleep? */
        /* FIXME: Replace by nanosleep, because its part of the standard library. */
        usleep( 20);  /* 20 µs since the sampel rate is 50 kHz.  */
      }
      break;
    default:
      break;
  }
  fclose(file);
}
