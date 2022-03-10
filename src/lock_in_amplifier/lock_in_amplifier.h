#ifndef LOCK_IN_AMPLIFIER_H
#define LOCK_IN_AMPLIFIER_H

#include "read_binary.h"
#include <stdlib.h>
#include <math.h>

struct filtered_data {
  double ac_1_X;
  double ac_1_Y;
  double ac_2_X;
  double ac_2_Y;
  double ac_3_X;
  double ac_3_Y;
};

void generate_references(struct raw_data *raw_data, double *sine_reference, double *cosine_reference);


void filter_signals(struct raw_data *raw_data, struct filtered_data *filtered_data, const double *sine_reference,
                    const double *cos_reference);

#endif /* LOCK_IN_AMPLIFIER_H */
