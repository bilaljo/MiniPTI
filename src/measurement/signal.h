
struct intensity_dc {
  double *detector_1;
  double *detector_2;
  double *detector_3;
};

struct point {
  double X;
  double Y;
};

struct intensity_ac {
  struct point *detector_1;
  struct point *detector_2;
  struct point *detector_3;
}