#ifndef SAVE_DATA_H
#define SAVE_DATA_H

#include <stdio.h>
#include "lock_in_amplifier.h"
#include "read_binary.h"

void save_data(struct ac_data *ac, struct dc_signal *dc, enum mode_t mode, FILE *file);

#endif /* SAVE_DATA_H */
