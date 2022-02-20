# Dependcies

## Debian and Ubuntu
```bash
sudo apt install curl gpg2
```

## Fedora
```bash
sudo dnf install curl gpg
```

## Arch Linux

```bash
sudo pacman -S curl gpg
```

# Linux Kernel
1. Download the current version of linux kernel from the *official* website and the signuature.
```bash
curl -OL https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.16.10.tar.xz
```

```bash
curl -OL https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.16.10.tar.sign
```

2. For us are the keys of Linus Torvalds and  Greg Kroah-Hartman important. First we check them current keys:
```bash
gpg --locate-keys torvalds@kernel.org gregkh@kernel.org
```
3. Now we can mark them as trusted
```bash
gpg --tofu-policy good ABAF11C65A2970B130ABE3C479BE3E4300411886  # Linus
gpg --tofu-policy good 647F28654894E3BD457199BE38DBBDC86092693E # Greg
```
Now we can run the verficiation without any warning
```bash
gpg --trust-model tofu --verify linux-5.16.10.tar.sign
```

For the kernel configuration we select the following options:

* 64-bit kernel
* Exectuable File Formats:
  * Kernel Support for ELF Binaries
  * Write ELF core dumps ...
  * Kernel support for scripts starting with #!

* General Setup
  * Compile the kernel with warnings as errors
  * Kernel Compressions Mode???
  * System V IPC
  * BSD Process accounting
  * Kernel .config support
  * Enable kernel headers through ...
  * Intial RAM filesystem
  * Boot config support
  * Enable Embedded System
* Processors type and featrues
  * Symmetric multi-processing support
  * Single-depth WCHAN output
* Device Drivers
  * PCI Support
* Networking Support
  * Networking Options
    * Unix domain sockets
    * Unix socket monitoring interface
    * TCP/IP networking
    * Network packet filtering framework
    * 802.1d Ethernet Bridging
* Device Drivers
   * I2C Support
   * GPIO Support
   * SCSI Device Support
      * SCSI Disk support
      * SCSI generic support
  * Network device support
    * Universal TUN/TAP device driver support
    * Ethernet driver support
* File Systems
    * Second extended fs support
    * Pseudo file system
      * tmpfs virtual memory file system support