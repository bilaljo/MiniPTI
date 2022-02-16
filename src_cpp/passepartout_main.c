#include <stddef.h>
#include <stdio.h>
#include <sys/time.h>
#include "readCSV.h"
#include "system_phases.h"

int main(void) {
  struct timeval  tv1, tv2;
  struct csv_file csv_file = {
    .names = {{0}},
    .data = {{0}},
  };
  gettimeofday(&tv1, NULL);
  get_phases(&system_phases, &intentities);
  gettimeofday(&tv2, NULL);
  printf ("Total time = %ld microseconds\n", (tv2.tv_usec - tv1.tv_usec) + (tv2.tv_sec - tv1.tv_sec));
  printf("\n%1.10f,%1.10f", system_phases[0], system_phases[1]);
  return 0;
}
