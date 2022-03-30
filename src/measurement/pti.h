#ifndef PTI_H
#define PTI_H

#define CHANNELS 3

struct ac_t {
  double X[CHANNELS];
  double Y[CHANNELS];
};

double calculate_pti_signal(double interferometric_phase, const double *output_phase, struct ac_t *ac,
                            const double *I_max, const double *I_min);

#endif  /* PTI_H */
