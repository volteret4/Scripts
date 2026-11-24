PKG     = gtk+-3.0 glib-2.0
CC      = gcc
CFLAGS  = -Wall -Wextra -fPIC -std=c99 -D_GNU_SOURCE \
          $(shell pkg-config --cflags $(PKG)) \
          -I/usr/include/deadbeef
LDFLAGS = -shared \
          $(shell pkg-config --libs $(PKG))
SOURCES = $(wildcard *.c)
OBJECTS = $(SOURCES:.c=.o)
TARGET  = ddb_infobar_ng.so

SCRIPTS_DEST = $(HOME)/.config/deadbeef/infobar_scripts
PLUGIN_DEST  = $(HOME)/.local/lib/deadbeef

.PHONY: all install clean

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) $^ -o $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

install: all
	install -Dm755 $(TARGET) $(PLUGIN_DEST)/$(TARGET)
	mkdir -p $(SCRIPTS_DEST)
	install -Dm755 ../letras_ovh.py    $(SCRIPTS_DEST)/letras_ovh.py
	install -Dm755 ../letras_genius.py $(SCRIPTS_DEST)/letras_genius.py
	install -Dm755 ../bio_artista.py   $(SCRIPTS_DEST)/bio_artista.py
	install -Dm755 ../info_album.py    $(SCRIPTS_DEST)/info_album.py
	install -Dm755 ../similares.py     $(SCRIPTS_DEST)/similares.py
	install -Dm755 ../sello.py         $(SCRIPTS_DEST)/sello.py
	install -Dm644 ../darkone_links.py $(SCRIPTS_DEST)/darkone_links.py
	@echo "Instalado. Reinicia DeaDBeeF para cargar el plugin."

clean:
	rm -f $(OBJECTS) $(TARGET)
