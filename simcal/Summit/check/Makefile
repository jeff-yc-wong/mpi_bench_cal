all: summit_check

SIMGRID_INSTALL_PATH = /usr/local
CC = g++ --std=c++17
CFLAGS = -g -O2 -Wall -Wextra

summit_check: summit_check.o
	$(CC) -L$(SIMGRID_INSTALL_PATH)/lib/ $(CFLAGS) $^ -lsimgrid -o $@

summit_check.o: summit_check.cpp
	$(CC) -I$(SIMGRID_INSTALL_PATH)/include  $(CFLAGS) -c -o  $@ $<

clean:
	rm -f summit_check *.o *~
.PHONY: clean
