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

void generate_references(const struct raw_data *raw_data, double *in_phase, double *quadratur);


void filter_signals(const struct raw_data *raw_data, struct ac_data *ac, const double *in_phase,
                    const double *quadratur);

void calculate_dc(struct dc_signal *dc_signal, struct  raw_data *raw_data);

void process_measurement(char *file_path, FILE *file);


#endif /* LOCK_IN_AMPLIFIER_H */
