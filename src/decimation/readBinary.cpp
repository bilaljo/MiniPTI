#include "readBinary.h"
#include <string>

decimation::rawData decimation::readBinary(std::ifstream &binaryData) {
  decimation::rawData data = {};
  char dc1Buffer[samples];
  char dc2Buffer[samples];
  char dc3Buffer[samples];
  char refBuffer[samples];
  char ac1Buffer[samples];
  char ac2Buffer[samples];
  char ac3Buffer[samples];
  binaryData.read(dc1Buffer, samples);
  binaryData.read(dc2Buffer, samples);
  binaryData.read(dc3Buffer, samples);
  binaryData.read(refBuffer, samples);
  binaryData.read(ac1Buffer, samples);
  binaryData.read(ac2Buffer, samples);
  binaryData.read(ac3Buffer, samples);
  for (int sampel = 0; sampel < decimation::samples; sampel++) {
    data.dc1[sampel] = static_cast<double>(dc1Buffer[sampel]);
    data.dc2[sampel] = static_cast<double>(dc2Buffer[sampel]);
    data.dc3[sampel] = static_cast<double>(dc3Buffer[sampel]);
    data.ref[sampel] = static_cast<double>(refBuffer[sampel]);
    data.ac1[sampel] = static_cast<double>(ac1Buffer[sampel]);
    data.ac2[sampel] = static_cast<double>(ac2Buffer[sampel]);
    data.ac3[sampel] = static_cast<double>(ac3Buffer[sampel]);
  }
  return data;
}
