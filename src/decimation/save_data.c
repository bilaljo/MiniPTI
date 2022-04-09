#include "save_data.h"

void save_data(struct ac_data *ac, struct dc_signal *dc, enum mode_t mode, FILE *file) {
  if (mode == BINARY) {
    fwrite(ac->X, sizeof(double), CHANNELS, file);
    fwrite(ac->Y, sizeof(double), CHANNELS, file);
    fwrite(dc, sizeof(double), CHANNELS, file);
  } else {
    for (int i = 0; i < CHANNELS; i++) {
      fprintf(file, "%1.10f,", ac->X[i]);
      fprintf(file, "%1.10f,", ac->Y[i]);
    }
    fprintf(file, "%1.10f,", dc->DC_1);
    fprintf(file, "%1.10f,", dc->DC_2);
    fprintf(file, "%1.10f,", dc->DC_3);
    fprintf(file, "\n");
  }
}
