Alien artwork (Lunar Alien Reaction)
====================================
The supplied evil/friendly pixel-art references are the primary game assets:

    evil_alien.png       evil (purple) target, with three red alert marks
    friendly_alien.png   friendly (green) distractor

Both files are RGBA, trimmed to their visible bounds and cleaned for smooth
scaling. They are loaded once at runtime; the game never recolours them.

Originals
---------
The untouched uploads are archived in:

    source/evil_alien.png
    source/friendly_alien.png

Do not edit the files in source/; rerun the cleaning tool after replacing them:

    python tools/clean_alien_assets.py

What the cleaner does
---------------------
* removes alpha 1-23 black haze and detached specks (the source images had a
  faint black noise field that produced a dark halo when smooth-scaled);
* keeps the real artwork, including the evil alien's detached alert marks;
* bleeds the character's own colours into transparent pixels so interpolation
  has no black to sample;
* trims transparent margins (evil 189x269, friendly 175x208) for a predictable
  aspect ratio.

Runtime placement
-----------------
* Shared 112 px box, aspect ratio preserved (evil ~79x112, friendly ~94x112).
* Shared mid-bottom anchor as the alien rises from a crater.
* Small contact shadow; no glow halo.
* Same artwork in the crater, gameplay legend and intro recognition key.
* If a file is missing, the procedural sprite is used and the intro shows a
  short notice.
