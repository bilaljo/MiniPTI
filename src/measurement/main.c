#include "read_csv.h"
#include "pti.h"

int main(void) {
  struct csv_t csv_file = {0};
  read_csv("build/test.csv", &csv_file);
  FILE *output = fopen("pti.csv", "a");
  if (! output) {
    return 1;
  }
  double scaled_pd[3];
  double min[CHANNELS] = {0};
  double max[CHANNELS] = {0};
  double output_phases[CHANNELS] = {0};
  double system_phases[CHANNELS] = {0};
  read_config(min, max, system_phases, output_phases);
  scaled_pd[0] = scale_signal(get_column(&csv_file, "PD1"), min[0], max[0]);
  scaled_pd[1] = scale_signal(get_column(&csv_file, "PD2"), min[1], max[1]);
  scaled_pd[2] = scale_signal(get_column(&csv_file, "PD3"), min[2], max[2]);
  struct ac_t ac = {0};
  ac.X[0] = get_column(&csv_file, "X1");
  ac.Y[0] = get_column(&csv_file, "X1");
  ac.X[1] = get_column(&csv_file, "X2");
  ac.Y[1] = get_column(&csv_file, "X2");
  ac.X[2] = get_column(&csv_file, "X3");
  ac.Y[2] = get_column(&csv_file, "X3");
  double interferometric_phase = calculate_interferomtic_phase(output_phases, scaled_pd);
  double pti_signal = calculate_pti_signal(interferometric_phase, output_phases, &ac, max, min, system_phases);
  fprintf(output, "%e", pti_signal);
  close_csv(&csv_file);
  fclose(output);
  return 0;
}
