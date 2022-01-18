#include "read_csv.h"
#include <stddef.h>
#include <stdio.h>

int main(void) {
  struct csv_file csv_file = {
    .names = {{0}},
    .data = {{0}},
  };
  size_t number_of_columns = get_names("data.csv", csv_file.names);
  for (int i = 0; i < number_of_columns - 1; i++) {
    printf("%s,", csv_file.names[i]);
  }
  printf("%s", csv_file.names[number_of_columns - 1]);
  get_data("data.csv", csv_file.data, number_of_columns);
  for (size_t i = 0; i < NUMBER_OF_COLUMNS; i++) {
    for (size_t j = 0; j < number_of_columns; j++) {
      printf("%e,", csv_file.data[i][j]);
    }
    printf("%e\n", csv_file.data[i][number_of_columns - 1]);
  }
  return 0;
}
