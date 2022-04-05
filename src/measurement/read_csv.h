#ifndef READ_CSV_H
#define READ_CSV_H

#include <stddef.h>
#include <stdio.h>
#include <string>

#define NAME_SIZE 50
#define COLUMNS 10
#define DIGITS 12
#define BUFFER_SIZE (DIGITS * COLUMNS)

struct csv_t {
  char names[COLUMNS][NAME_SIZE];
  size_t numer_of_columns;
  double data[COLUMNS];
  FILE *csv;
};

struct csv_t *read_csv(std::string file_name, struct csv_t *csv_file);

double get_column(struct csv_t *csv_file, char *column);

FILE *save_data(const char *file_name, double (*data)[2]);

void close_csv(struct csv_t *csv_file);

#endif /* READ_CSV_H */
