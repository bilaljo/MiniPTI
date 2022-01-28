#!/usr/bin/bash

BINUTILS="https://ftp.gnu.org/gnu/binutils/binutils-2.37.tar.gz"
GCC="https://ftp.gnu.org/gnu/gcc/gcc-6.4.0/gcc-6.4.0.tar.gz"
GDB="https://ftp.gnu.org/gnu/gdb/gdb-11.2.tar.gz"
NEW_LIB="https://sourceware.org/pub/newlib/newlib-4.2.0.20211231.tar.gz"

BINUTILS_ARCHIV=$(echo $BINUTILS | cut -d '/' -f 6)
GCC_ARCHIV=$(echo $GCC | cut -d '/' -f 7)
GDB_ARCHIV=$(echo $GDB | cut -d '/' -f 6)
NEW_LIB_ARCHIV=$(echo $NEW_LIB | cut -d '/' -f 6)

TARGET=arm-none-eabi
PREFIX=/home/$whoami/arm-none-abi
CPU=cortex-m4
ARM_FLAGS=--with-no-thumb-interwork --with-mode=thumb
CONFIGURE_BINUTILS=--target=$TARGET --prefix=$PREFIX --with-cpu=$CPU $ARM_FLAGS

#wget $BINUTILS $GCC $GDB

tar -xvzf $BINUTILS_ARCHIV
tar -xvzf $GCC_ARCHIV
tar -xvzf $GDB_ARCHIV
tar -xvzf $NEW_LIB_ARCHIV

sudo mkdir -p ~/toolchain/build/binutils-build
cd ~/toolchain/build/binutils-build
~/$(echo $BINUTILS_ARCHIV | cut -d ".tar" -f 1)/configure $CONFIGURE_BINUTILS
make all install 2>&1 | tee ~/toolchain/build/binutils-build/binutils-build-logs.log

export PATH="$PATH:/home/$whoami/arm-none-eabi/bin"

sudo mkdir -p ~/toolchain/build/gcc-build
cd ~/toolchain/build/gcc-build
~/$(echo $GCC_ARCHIV | cut -d ".tar" -f 1)/configure --target=$TARGET --prefix=$PREFIX \
--enable-languages=c,c++ --without-headers --with-newlib $ARM_FLAGS
make all-gcc install-gcc 2>&1 | tee ./gcc-build-withoutnewlib-logs.log

sudo mkdir -p ~/toolchain/build/newlib-build
cd ~/toolchain/build/newlib-build
~/$(echo $NEW_LIB_BUILD | cut -d ".tar" -f 1)/configure --target=$TARGET --prefix=$PREFIX \
--disable-newlib-supplied-syscalls
make all install 2>&1 | tee ./newlib-build-logs.log

sudo mkdir ~/toolchain/build/gcc-build
cd ~/toolchain/build/gcc-build
~/$(echo $GCC_ARCHIV | cut -d ".tar" -f 1)/configure --target=$TARGET --prefix=$PREFIX --with-cpu=$CPU \
--enable-languages=c,c++ --with-newlib $ARM_FLAGS
make all-gcc install-gcc 2>&1 | tee ./gcc-build-withnewlib-logs.log

sudo mkdir ~/toolchain/build/gdb-build
cd ~/toolchain/build/gdb-build
~/$(echo $GDB_ARCHIV | cut -d ".tar" -f 1)/configure --target=$TARGET --prefix=$PREFIX
make all install 2>&1 | tee ./gdb-build-logs.log
