#!/bin/bash
for f in *.orig.jpg; do
  [ -e "$f" ] || continue
  base="${f%.orig.jpg}"

  convert "$f" \
    -resize 480x480^ \
    -gravity center \
    -extent 480x480 \
    "${base}.jpg"
done

