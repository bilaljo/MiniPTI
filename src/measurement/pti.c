#include "pti.h"
#include <math.h>
#include <stddef.h>

#define COMBINATIONS 6

struct indices_t {
  int x[3];
  int y[3];
};

void min_max(const double *dc_signal, double *min, double *max) {
  for (int i = 0; i < sizeof (dc_signal) / (dc_signal[0]); i++) {
    *min = dc_signal[i] < *min ? dc_signal[i] : *min;
    *max = dc_signal[i] < *max ? dc_signal[i] : *max;
  }
}

void scale_signal(double *dc_signal, double min, double max) {
  for (int i = 0; i < sizeof (dc_signal) / (dc_signal[0]); i++) {
    dc_signal[i] = 2 * (dc_signal[i] - min) / (max - min) - 1;
  }
}

double mean(const double *data, size_t size) {
  double current_mean = 0;
  for (int i = 0; i < size; i++) {
    current_mean += data[i];
  }
  return current_mean / (double)size;
}

double calculate_interferomtic_phase(const double *outputphase, const double *dc_scaled) {
  double x[COMBINATIONS] = {0};
  double y[COMBINATIONS] = {0};
  for (int i = 0; i < 3; i++) {
    x[i] = dc_scaled[i] * cos(outputphase[i]) + sqrt(1 - pow(dc_scaled[i], 2)) * sin(outputphase[i]);
    y[i] = dc_scaled[i] * sin(outputphase[i]) + sqrt(1 - pow(dc_scaled[i], 2)) * cos(outputphase[i]);
  }
  for (int i = 3; i < COMBINATIONS; i++) {
    x[i] = dc_scaled[i] * cos(outputphase[i - 3]) - sqrt(1 - pow(dc_scaled[i], 2))
                                                    * sin(outputphase[i - 3]);
    y[i] = dc_scaled[i] * sin(outputphase[i - 3]) - sqrt(1 - pow(dc_scaled[i], 2))
                                                    * cos(outputphase[i - 3]);
  }
  double error_x = 6;
  double error_y = 6;
  double current_error_x = 6;
  double current_error_y = 6;
  struct indices_t indices = {0};
  for (int i = 0; i < COMBINATIONS; i++) {
    for (int j = i + 1; j < COMBINATIONS; j++) {
      for (int k = j + 1; k < COMBINATIONS; k++) {
        error_x = fabs(x[i] - x[k]) + fabs(x[j] - x[i]) + fabs(x[j] - x[k]);
        error_y = fabs(y[i] - y[k]) + fabs(y[j] - y[i]) + fabs(y[j] - y[k]);
        if (current_error_x > error_x) {
          indices.x[0] = i;
          indices.x[1] = j;
          indices.x[2] = k;
        }
        if (current_error_y > error_y) {
          indices.y[0] = i;
          indices.y[1] = j;
          indices.y[2] = k;
        }
      }
    }
  }
  double x_results[3];
  double y_results[3];
  for (int i = 0; i < 3; i++) {
    x_results[i] = x[indices.x[i]];
    y_results[i] = y[indices.y[i]];
  }
  double x_value = mean(x_results, 3);
  double y_value = mean(y_results, 3);
  return atan2(y_value, x_value);
}

double theta_star = 0;

double calculate_pti_signal(const double interferometric_phase, const double *output_phase, struct ac_t *ac,
                          const double *I_max, const double *I_min) {
  double pti_signal = 0;
  double weight = 0;
  for (int i = 0; i < CHANNELS; i++) {
    int sign = sin(interferometric_phase - output_phase[i]) >= 0 ? 1 : -1;
    double R = sqrt(ac->X[i] + ac->Y[i]);
    double system_phase = atan2(ac->Y[i], ac->Y[i]);
    double dms = R * cos(system_phase - theta_star);
    pti_signal += dms * sign;
    weight += (I_max[i] - I_min[i]) / 2 * fabs(sin(interferometric_phase - output_phase[i]));
  }
  return pti_signal / weight;
}
