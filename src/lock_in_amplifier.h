#ifndef LOCK_IN_AMPLIFIER_H
#define LOCK_IN_AMPLIFIER_H

struct lock_in_amplifier {
  double X;
  double Y;
  double reference_signal;
};

struct AC_Signal {
  struct lock_in_amplifier detector_1;
  struct lock_in_amplifier detector_2;
  struct lock_in_amplifier detector_3;
};

#endif // LOCK_IN_AMPLIFIER_H
