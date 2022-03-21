#include "save_data.h"
#define MEMBERS 7

void save_data(struct ac_data *ac, struct dc_signal *dc, FILE *file) {
  switch (mode) {
    case NORMAL:
    case ONLINE:
      fwrite(&ac, sizeof(ac), MEMBERS * sizeof(double), file);
      fwrite(&dc, sizeof(dc), MEMBERS * sizeof(double), file);
      break;
    case DEBUG:
    case VERBOSE:
      for (int i = 0; i < CHANNELS; i++) {
        fprintf(file, "%1.10f,", ac->X[i]);
        fprintf(file, "%1.10f,", ac->Y[i]);
      }
      fprintf(file, "\n");
      break;
  }
  fclose(file);
}
