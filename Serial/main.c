#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

#define SERIAL_BUFFER_SIZE 4096

int main(int argc, char** argv) {
  if (argc != 2) {
    return -1;
  }
  char *serial_port_name = argv[1];
  int serial_port_fd = open(serial_port_name, O_RDWR);
  if (!mkfifo("/tmp/data.fifo")) {
    return -1;
  }
  int fifo_fd = open("/tmp/data.fifo", O_WRONLY);
  char buffer[SERIAL_BUFFER_SIZE];
  while (1) {
    read(serial_port_fd, buffer, SERIAL_BUFFER_SIZE;)
    write(fifo_fd, buffer, SERIAL_BUFFER_SIZE);
  }
  return 0;
}
