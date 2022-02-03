#!/usr/bin/bash

GSL="https://mirror.ibcp.fr/pub/gnu/gsl/gsl-2.7.1.tar.gz"

GSL_ARCHIV=$(echo $GSL | cut -d '/' -f 7)

wget $GSL
tar -xvzf $GSL_ARCHIV
rm -r $GSL_ARCHIV

COMPILER="arm-none-eabi-gcc"
LINKER="arm-none-eabi-gcc"
DIRECTORY="/home/$(whoami)/gsl"
ARCHTECTURE="armv7e-m"
CFLAGS="-mthumb -march=$ARCHTECTURE -mfpu=fpv4-sp-d16 -mfloat-abi=hard"
LFLAGS="--specs=nano.specs --specs=nosys.specs $CFLAGS"
HOST="x86_64-unknown-linux-gnu"

cd ~/$(basename $GSL_ARCHIV .tar.gz)
~/$(basename $GSL_ARCHIV .tar.gz)/configure --prefix=$DIRECTORY CC=$COMPILER CXX=$COMPILER LD=$LINKER CCFLAGS="$CFLAGS" CXXFLAGS="$CFLAGS" \
                                            LDFLAGS="$LFLAGS" --host=$HOST
make clean
make install

