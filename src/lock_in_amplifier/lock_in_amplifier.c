#include "lock_in_amplifier.h"

void generate_references(struct raw_data *raw_data, double *sine_reference, double *cosine_reference) {
  double period = 0;
  int signals = 0;
  double last_time = 0;
  /* Since the clock can slightly jitter we have to calculate the middle perioid of our signal. */
  for (size_t i = 59; i < SAMPLES - 1; i++) {
    /* If we arive a rising edge we have change from low (below 1 / 10) to high (over 9 / 10).
     * The period is know the difference between the last seen tranisition and the current time.
    */
    if (raw_data->reference[i + 1] < 1.0 / 10 && raw_data->reference[i] > 9.0 / 10) {
      period += (i - last_time);
      last_time = i;
      signals++;
    }
  }
  if (! signals) {
    fprintf(stderr, "Error: No modulation signal has occoured.\n");
    exit(1);
  }
  period /= (double)signals;
  for (size_t i = 0; i < SAMPLES; i++) {
    sine_reference[i] = sin(2 * M_PI / period * i / SAMPLES);
    cosine_reference[i] = cos(2 * M_PI / period * i / SAMPLES);
  }
}

void filter_signals(struct raw_data *raw_data, struct filtered_data *filtered_data, const double *sine_reference,
                    const double *cos_reference) {
  for (size_t i = 0; i < SAMPLES; i++) {
    filtered_data->ac_1_X += raw_data->ac_1[i] * sine_reference[i];
    filtered_data->ac_1_Y += raw_data->ac_1[i] * cos_reference[i];
    filtered_data->ac_2_X += raw_data->ac_2[i] * sine_reference[i];
    filtered_data->ac_2_Y += raw_data->ac_2[i] * cos_reference[i];
    filtered_data->ac_3_X += raw_data->ac_3[i] * sine_reference[i];
    filtered_data->ac_3_Y += raw_data->ac_3[i] * cos_reference[i];
  }
  filtered_data->ac_1_X /= SAMPLES ;
  filtered_data->ac_1_Y /= SAMPLES;
  filtered_data->ac_2_X /= SAMPLES;
  filtered_data->ac_2_Y /= SAMPLES;
  filtered_data->ac_3_X /= SAMPLES;
  filtered_data->ac_3_Y /= SAMPLES;
}
