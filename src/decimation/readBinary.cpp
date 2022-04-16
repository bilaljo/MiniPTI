#include "readBinary.h"
#include <string>

decimation::rawData decimation::readBinary(std::ifstream &binaryData) {
  decimation::rawData data = {};
  int sizeInformation;
  // Labview problem.
  binaryData.read(reinterpret_cast<char*>(&sizeInformation), sizeof(int));
  binaryData.read(reinterpret_cast<char*>(&sizeInformation), sizeof(int));
  // The actual data.
  binaryData.read(reinterpret_cast<char*>(&data.dc1), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.dc2), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.dc3), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.ref), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.ac1), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.ac2), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(&data.ac3), sizeof(double) * decimation::samples);
  return data;
}
