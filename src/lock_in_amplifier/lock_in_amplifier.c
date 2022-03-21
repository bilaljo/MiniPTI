#include "lock_in_amplifier.h"
#include "save_data.h"
#include <stdbool.h>

#define AMPLIFICATION 1000
#define DATA_SIZE 1700

void generate_references(const struct raw_data *raw_data, double *in_phase, double *quadratur) {
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
    if (mode == DEBUG || mode == VERBOSE) {
      fprintf(stderr, "Error: No modulation signal has occoured.\n");
    }
    exit(1);
  }
  period /= (double)signals;
  for (int i = 0; i < SAMPLES; i++) {
    in_phase[i] = sin(2 * M_PI / period  * (double)(i - phase_shift));
    quadratur[i] = cos(2 * M_PI / period * (double)(i - phase_shift));
  }
}

void filter_signals(const struct raw_data *raw_data, struct ac_data *ac, const double *in_phase,
                    const double *quadratur) {
  for (size_t i = 0; i < SAMPLES; i++) {
    ac->X[0] += raw_data->ac_1[i] * in_phase[i];
    ac->Y[0] += raw_data->ac_1[i] * quadratur[i];
    ac->X[1] += raw_data->ac_2[i] * in_phase[i];
    ac->Y[1] += raw_data->ac_2[i] * quadratur[i];
    ac->X[2] += raw_data->ac_3[i] * in_phase[i];
    ac->Y[2] += raw_data->ac_3[i] * quadratur[i];
  }
  ac->X[0] /= (SAMPLES * AMPLIFICATION) ;
  ac->Y[0] /= (SAMPLES * AMPLIFICATION);
  ac->X[1] /= (SAMPLES * AMPLIFICATION);
  ac->Y[1] /= (SAMPLES * AMPLIFICATION);
  ac->X[2] /= (SAMPLES * AMPLIFICATION);
  ac->Y[2] /= (SAMPLES * AMPLIFICATION);
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

void process_measurement(char *file_path, FILE *file) {
  FILE *binary_file = open_file(file_path);
  double sine_reference[SAMPLES] = {0};
  double cosine_reference[SAMPLES] = {0};
  struct raw_data raw_data = {0};
  struct ac_data ac = {0};
  struct dc_signal dc = {0};
  switch (mode) {
    case DEBUG:
    case NORMAL:
    case VERBOSE:
      for (int second = 0; second < DATA_SIZE; second++) {
        get_measurement(&raw_data, binary_file);
        generate_references(&raw_data, sine_reference, cosine_reference);
        filter_signals(&raw_data, &ac, sine_reference, cosine_reference);
        calculate_dc(&dc, &raw_data);
        save_data(&ac, &dc, file);
      }
      break;
    case ONLINE:
      get_measurement(&raw_data, binary_file);
      generate_references(&raw_data, sine_reference, cosine_reference);
      filter_signals(&raw_data, &ac, sine_reference, cosine_reference);
      calculate_dc(&dc, &raw_data);
      save_data(&ac, &dc, file);
      break;
    default:
      break;
  }
}
