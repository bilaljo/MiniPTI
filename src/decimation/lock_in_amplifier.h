#ifndef LOCK_IN_AMPLIFIER_H
#define LOCK_IN_AMPLIFIER_H

#include "read_binary.h"
#include <stdlib.h>
#include <math.h>

#define CHANNELS 3

struct ac_data {
  double X[CHANNELS];
  double Y[CHANNELS];
};

struct dc_signal {
  double DC_1;
  double DC_2;
  double DC_3;
};

void process_measurement(FILE *binary_file, enum mode_t mode, FILE *output);

#endif /* LOCK_IN_AMPLIFIER_H */
