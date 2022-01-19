#ifndef SYSTEM_PHASES_H
#define SYSTEM_PHASES_H

#include <stddef.h>

#define DATA_SIZE 2824

struct intensity {
  double detector_1;
  double detector_2;
  double detector_3;
};

void set_intensities(double (*intensity_1)[DATA_SIZE], double (*intensity_2)[DATA_SIZE],
                    double (*intensity_3)[DATA_SIZE], struct intensity (*intensties)[DATA_SIZE]);

void get_phases(double (*system_phases)[2], struct intensity (*intensities)[DATA_SIZE]);

#endif /* SYSTEM_PHASES_H */
