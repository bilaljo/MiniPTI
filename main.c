#include "read_csv.h"
#include <stddef.h>
#include <stdio.h>

int main(void) {
  char names[NUMBER_OF_ROWS][NAME_SIZE] = {{0}};
  size_t number_of_columns = get_names("data.csv", names);
  for (int i = 0; i < number_of_columns - 1; i++) {
    printf("%s,", names[i]);
  }
  printf("%s", names[number_of_columns - 1]);
  return 0;
}
