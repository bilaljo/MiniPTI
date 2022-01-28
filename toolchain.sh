#!/usr/bin/bash

BINUTILS="https://ftp.gnu.org/gnu/binutils/binutils-2.37.tar.gz"
GCC="https://ftp.gnu.org/gnu/gcc/gcc-6.4.0/gcc-6.4.0.tar.gz"
GDB="https://ftp.gnu.org/gnu/gdb/gdb-11.2.tar.gz"
NEW_LIB="https://sourceware.org/pub/newlib/newlib-4.2.0.20211231.tar.gz"
GSL="https://mirror.ibcp.fr/pub/gnu/gsl/gsl-2.7.1.tar.gz"

BINUTILS_ARCHIV=$(echo $BINUTILS | cut -d '/' -f 6)
GCC_ARCHIV=$(echo $GCC | cut -d '/' -f 7)
GDB_ARCHIV=$(echo $GDB | cut -d '/' -f 6)
NEW_LIB_ARCHIV=$(echo $NEW_LIB | cut -d '/' -f 5)
GSL_ARCHIV=$(echo $GSL | cut -d '/' -f 7)

TARGET="arm-none-eabi"
PREFIX="/home/($whoami)/arm-none-abi"
CPU=cortex-m4
ARM_FLAGS="--with-no-thumb-interwork --with-mode=thumb"
CONFIGURE_BINUTILS="--target=$TARGET --prefix=$PREFIX --with-cpu=$CPU $ARM_FLAGS"

wget $BINUTILS $GCC $GDB $NEW_LIB $GSL

tar -xvzf $BINUTILS_ARCHIV
tar -xvzf $GCC_ARCHIV
tar -xvzf $GDB_ARCHIV
tar -xvzf $NEW_LIB_ARCHIV
tar -xvzf $GSL_ARCHIV

# Cross compile binutils
mkdir -p ~/toolchain/build/binutils-build
echo $pwd
cd ~/toolchain/build/binutils-build
~/$(basename $BINUTILS_ARCHIV .tar.gz)/configure $CONFIGURE_BINUTILS
make all install 2>&1 | tee ./binutils-build-logs.log

export PATH="$PATH:/home/($whoami)/arm-none-eabi/bin"

# Cross compile gcc
mkdir -p ~/toolchain/build/gcc-build
cd ~/toolchain/build/gcc-build
~/"$(basename $GCC_ARCHIV .tar.gz)"/configure --target=$TARGET --prefix=$PREFIX \
--enable-languages=c,c++ --without-headers --with-newlib $ARM_FLAGS
make all-gcc install-gcc 2>&1 | tee ./gcc-build-logs.log

# Cross compile newlib
mkdir -p ~/toolchain/build/newlib-build
cd ~/toolchain/build/newlib-build
~/$(basename $NEW_LIB_ARCHIV .tar.gz)/configure --target=$TARGET --prefix=$PREFIX \
--disable-newlib-supplied-syscalls
make all install 2>&1 | tee ./newlib-build-logs.log

# Cross compile gcc again with newlib
mkdir ~/toolchain/build/gcc-build
cd ~/toolchain/build/gcc-build
~/$(basename $GCC_ARCHIV .tar.gz)/configure --target=$TARGET --prefix=$PREFIX --with-cpu=$CPU \
--enable-languages=c,c++ --with-newlib $ARM_FLAGS
make all-gcc install-gcc 2>&1 | tee ./gcc-build-logs.log

# Cross compile gdb
mkdir ~/toolchain/build/gdb-build
cd ~/toolchain/build/gdb-build
~/$(basename $GDB_ARCHIV .tar.gz)/configure --target=$TARGET --prefix=$PREFIX
make all install 2>&1 | tee ./gdb-build-logs.log

# Cross compile the gsl
mkdir ~/toolchain/build/gsl-build
cd ~/toolchain/build/gsl-build
~/$(basename $GSL_ARCHIV .tar.gz)/configure --target=$TARGET --prefix=$PREFIX $ARM_FLAGS
make all install 2>&1 | tee ./gsl-build-logs.log
