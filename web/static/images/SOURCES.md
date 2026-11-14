# Human silhouette source

`human-silhouette.svg` is the unmodified **Male body silhouette** SVG from Openclipart item 82639, downloaded 14 November 2026.

- **Source page:** https://openclipart.org/detail/82639/male-body-silhouette
- **Direct SVG:** https://openclipart.org/download/82639/body-shape.svg
- **Author:** mlampret (the Openclipart metadata describes it as a symmetrical remix of “Male body silhouette”)
- **License:** Creative Commons Zero 1.0 / public-domain dedication. Openclipart states that its clipart is released to the public domain under CC0, including permission to reproduce, distribute, modify, and use commercially: https://openclipart.org/share
- **SHA-256:** `0deff48bf3409b7f3c3c0d42730242f69908d9d80c68d270d1130f7642cda325`

## Geometry and reuse

The source has native `viewBox="0 0 278.8 984.46"`, no explicit width/height, and one silhouette path (`id="path3547"`) inside `g#layer1` with the source transform `translate(-37.897 -34.052)`. The path uses `fill:#f0f0f0` and `stroke:#000000;stroke-width:2.7111`. The complete head, both separated arms/hands, both legs, and both feet are inside this native frame; the rendered ink bounds leave clear margins on every edge.

Reuse the asset as a whole, preserving the native viewBox and the complete group/path hierarchy. Do not extract body parts, crop the file, alter its path, or add a clipPath/mask around it. Put any AURA-Bio symbolic overlays in a sibling layer above the intact silhouette, using the same outer coordinate system; if embedding it in an SVG wrapper, use `viewBox="0 0 278.8 984.46"` and preserve the default aspect ratio rather than changing the silhouette geometry.

## History

The replaced prior source was Wikimedia Commons **Human body silhouette.svg**, attributed to Mikael Häggström with SVG modification by RexxS, public domain, SHA-256 `d0e37b1a7b06c9db1e4c822c3b5189f3d9da4335cd2c543d04ec2e255ed49f9e`, from https://commons.wikimedia.org/wiki/File:Human_body_silhouette.svg and https://upload.wikimedia.org/wikipedia/commons/f/f4/Human_body_silhouette.svg. It was replaced because the requested design needed a different complete-body silhouette source, not the previously cropped-parts treatment.

## Console composition

`body-systems.svg` uses the same native viewBox and the complete original `layer1` group, transform, path data and path attributes. There is no clipPath, mask, silhouette extraction or cut-out. Presentation CSS lets the whole source figure inherit the bone/muscle status color; head and torso selectors sit above it, and habitat/radiation uses the surrounding frame. The complete figure remains present under every overlay, including neck, shoulders, hands and feet. These are symbolic system controls, not anatomical diagnosis. A unit test pins the original checksum, every original path attribute and transform, and forbids clipping/masking.
