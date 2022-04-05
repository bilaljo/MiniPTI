#ifndef PTI_H
#define PTI_H

#define CHANNELS 3

struct ac_t {
  double X[CHANNELS];
  double Y[CHANNELS];
};

double scale_signal(double dc_signal, double min, double max);

double calculate_interferomtic_phase(const double *outputphase, const double *dc_scaled);

double calculate_pti_signal(double interferometric_phase, const double *output_phase, struct ac_t *ac,
                            const double *I_max, const double *I_min, double *system_phase);

#endif  /* PTI_H */
