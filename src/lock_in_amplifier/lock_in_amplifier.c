#include "lock_in_amplifier.h"
#include <stdbool.h>

#define AMPLIFICATION 1000

void generate_references(struct raw_data *raw_data, double *sine_reference, double *cosine_reference) {
  double period = 0;
  int signals = 0;
  int last_time = 0;
  int phase_shift = 0;
  bool first_run = true;
  /* Since the clock can slightly jitter we have to calculate the middle perioid of our signal. */
  for (int sample = 0; sample < SAMPLES - 1; sample++) {
    /* If we arive a rising edge we have change from low (below 1 / 10) to high (over 9 / 10).
     * The period is know the difference between the last seen tranisition and the current time.
    */
    if (raw_data->reference[sample + 1] < 1.0 / 10 && raw_data->reference[sample] > 9.0 / 10) {
      last_time = sample;
      if (first_run) {
        phase_shift = sample;
        first_run = false;
      }
    } else if (raw_data->reference[sample] < 1.0 / 10 && raw_data->reference[sample + 1] > 9.0 / 10
               && sample > phase_shift) {
      period += 2.0 * (sample - last_time);
      signals++;
    }
  }
  if (! signals) {
    fprintf(stderr, "Error: No modulation signal has occoured.\n");
    exit(1);
  }
  period /= (double)signals;
  for (int i = 0; i < SAMPLES; i++) {
    sine_reference[i] = sin(2 * M_PI / period  * (double)(i - phase_shift));
    cosine_reference[i] = cos(2 * M_PI / period * (double)(i - phase_shift));
  }
}

void filter_signals(struct raw_data *raw_data, struct filtered_data *filtered_data, const double *sine_reference,
                    const double *cos_reference) {
  for (size_t i = 0; i < SAMPLES; i++) {
    filtered_data->ac_1_Y += raw_data->ac_1[i] * cos_reference[i];
    filtered_data->ac_1_X += raw_data->ac_1[i] * sine_reference[i];
    filtered_data->ac_2_Y += raw_data->ac_2[i] * cos_reference[i];
    filtered_data->ac_2_X += raw_data->ac_2[i] * sine_reference[i];
    filtered_data->ac_3_Y += raw_data->ac_3[i] * cos_reference[i];
    filtered_data->ac_3_X += raw_data->ac_3[i] * sine_reference[i];
  }
  filtered_data->ac_1_X /= (SAMPLES * AMPLIFICATION) ;
  filtered_data->ac_1_Y /= (SAMPLES * AMPLIFICATION);
  filtered_data->ac_2_X /= (SAMPLES * AMPLIFICATION);
  filtered_data->ac_2_Y /= (SAMPLES * AMPLIFICATION);
  filtered_data->ac_3_X /= (SAMPLES * AMPLIFICATION);
  filtered_data->ac_3_Y /= (SAMPLES * AMPLIFICATION);
}

void calculate_dc(struct dc_signal *dc_signal, struct  raw_data *raw_data) {
  for (int i = 0; i < SAMPLES; i++) {
    dc_signal->DC_1 += raw_data->dc_1[i];
    dc_signal->DC_2 += raw_data->dc_2[i];
    dc_signal->DC_3 += raw_data->dc_3[i];
  }
  dc_signal->DC_1 /= SAMPLES;
  dc_signal->DC_2 /= SAMPLES;
  dc_signal->DC_3 /= SAMPLES;
}
