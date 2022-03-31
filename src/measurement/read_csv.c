#include "read_csv.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static void get_names(FILE *file, struct csv_t *csv_file) {
  char line[BUFFER_SIZE];
  fgets(line, BUFFER_SIZE, file);
  if (line[strlen(line) - 1] == '\n') {
    line[strlen(line) - 1] = '\0';
  }
  char *sub_string = strtok(line, ",");
  for (int i = 0; i < COLUMNS && sub_string; i++) {
    strcpy(csv_file->names[i], sub_string);
    sub_string = strtok(NULL, ",");
    csv_file->numer_of_columns++;
  }
}

static void get_data(FILE *file, struct csv_t *csv_file) {
  char line[BUFFER_SIZE];
  char *end;
  fgets(line, BUFFER_SIZE, file);
  csv_file->data[0] = strtod(line, &end);
  for (int i = 1; i < csv_file->numer_of_columns; i++) {
    csv_file->data[i] = strtod(line + strlen(line) - strlen(end) + 1, &end);
  }
}

double get_column(struct csv_t *csv_file, char *column) {
  for (size_t i = 0; i < csv_file->numer_of_columns; i++) {
    if (! strcmp(csv_file->names[i], column)) {
      return csv_file->data[i];
    }
  }
}

struct csv_t *read_csv(char *file_name, struct csv_t *csv_file) {
  csv_file->csv = fopen(file_name, "r");
  if (csv_file->csv == NULL) {
    perror("Error");
    return NULL;
  }
  get_names(csv_file->csv, csv_file);
  get_data(csv_file->csv, csv_file);
  fclose(csv_file->csv);
  return csv_file;
}

FILE *save_data(const char *file_name, double (*data)[2]) {
  FILE *file = fopen(file_name, "w");
  if (file == NULL) {
    fprintf(stderr, "Error: Could not write file.\n");
    return NULL;
  }
  fprintf(file, "Phase 1,Phase 2\n");
  fprintf(file, "%1.10f,%1.10f\n", (*data)[0], (*data)[1]);
  return file;
}

void close_csv(struct csv_t *csv_file) {
  fclose(csv_file->csv);
}