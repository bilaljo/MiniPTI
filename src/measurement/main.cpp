#include <variant>
#include <string>
#include "read_csv.h"
#include "pti.h"
#include "config.h"

int main() {
  struct csv_t csv_file = {0};
  Config pti_config("pti.conf");
  read_csv(std::get<std::string>(pti_config["Filepath"]["PTI_Inversion"]), &csv_file);
  FILE *output = fopen("pti.csv", "aw");
  if (! output) return 1;
  double scaled_pd[3];
  double min[CHANNELS] = {std::get<double>(pti_config["Min_Values"]["Detector_1"]),
                          std::get<double>(pti_config["Min_Values"]["Detector_2"]),
                          std::get<double>(pti_config["Min_Values"]["Detector_3"])};
  double max[CHANNELS] = {std::get<double>(pti_config["Max_Values"]["Detector_1"]),
                          std::get<double>(pti_config["Max_Values"]["Detector_2"]),
                          std::get<double>(pti_config["Max_Values"]["Detector_3"])};
  double output_phases[CHANNELS] = {std::get<double>(pti_config["Output_Phases"]["Detector_1"]),
                                    std::get<double>(pti_config["Output_Phases"]["Detector_2"]),
                                    std::get<double>(pti_config["Output_Phases"]["Detector_3"])};
  double system_phases[CHANNELS] = {std::get<double>(pti_config["System_Phases"]["Detector_1"]),
                                    std::get<double>(pti_config["System_Phases"]["Detector_2"]),
                                    std::get<double>(pti_config["System_Phases"]["Detector_3"])};
  scaled_pd[0] = scale_signal(get_column(&csv_file, (char*)"PD1"), min[0], max[0]);
  scaled_pd[1] = scale_signal(get_column(&csv_file, (char*)"PD2"), min[1], max[1]);
  scaled_pd[2] = scale_signal(get_column(&csv_file, (char*)"PD3"), min[2], max[2]);
  struct ac_t ac = {0};
  ac.X[0] = get_column(&csv_file, (char*)"X1");
  ac.Y[0] = get_column(&csv_file, (char*)"X1");
  ac.X[1] = get_column(&csv_file, (char*)"X2");
  ac.Y[1] = get_column(&csv_file, (char*)"X2");
  ac.X[2] = get_column(&csv_file, (char*)"X3");
  ac.Y[2] = get_column(&csv_file, (char*)"X3");
  double interferometric_phase = calculate_interferomtic_phase(output_phases, scaled_pd);
  double pti_signal = calculate_pti_signal(interferometric_phase, output_phases, &ac, max, min, system_phases);
  fprintf(output, "%e", pti_signal);
  close_csv(&csv_file);
  return 0;
}
