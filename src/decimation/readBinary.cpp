#include "readBinary.h"
#include <string>
#include <iostream>

void decimation::readBinary(std::ifstream &binaryData, rawData& rawData) {
  int sizeInformation;
  // Labview problem.
  binaryData.read(reinterpret_cast<char*>(&sizeInformation), sizeof(int));
  binaryData.read(reinterpret_cast<char*>(&sizeInformation), sizeof(int));
  // The actual data.
  binaryData.read(reinterpret_cast<char*>(rawData.dc1.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.dc2.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.dc3.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.ref.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.ac1.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.ac2.data()), sizeof(double) * decimation::samples);
  binaryData.read(reinterpret_cast<char*>(rawData.ac3.data()), sizeof(double) * decimation::samples);
}
