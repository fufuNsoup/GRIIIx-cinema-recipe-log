# Flashing, and going back to stock

> There is **no confirmed recovery method** if a GR IIIx stops booting after a flash. The builds here were flashed and
> used without problems, but on only a few cameras. If you aren't comfortable with that risk, don't flash.

## Which cameras

GR IIIx on firmware **1.60** only. Ricoh's 1.60 file covers the GR IIIx, the **Urban Edition** and the **HDF**. The
Diary and other editions are a factory setting inside the same firmware. Stage 5 was confirmed on a standard, an Urban
Edition and a Diary Edition. The HDF uses the same file, but none of these builds has been flashed on one yet.

* On an older version, update with Ricoh's 1.60 first.
* On a newer version, **don't flash this.** The addresses only fit 1.60.
* Doesn't work on the GR III or GR IV (the camera rejects the file).

## Before flashing

- [ ] Your file's SHA-256 matches `stage11` in [`expected-hashes.txt`](../expected-hashes.txt):
      `shasum -a 256 FWDC243B.BIN` → `45cb3826…`
- [ ] Battery fully charged
- [ ] SD card formatted **in the camera**
- [ ] Ricoh's original `fwdc243b.bin` saved somewhere safe. This is your way back.
- [ ] Your U1/U2/U3 settings noted

## Flash

1. Copy `FWDC243B.BIN` to the root of the card. Keep the name exactly as it is.
2. Setup menu → firmware update. It offers 1.60 → 1.60, which is expected.
3. Don't touch anything until the camera restarts. Then delete the file from the card.

Moving between stages 2–11 needs no preparation.

## ⚠️ Going back to stock (mandatory steps)

The Cinema looks are new internal tones (25 / 26), and Grain is stored in a field that stock firmware has no menu for.
If either is still set when you flash stock, stock firmware reads past its look table (expect a broken live view or a
crash), or keeps applying grain with no way to turn it off.

1. **Stills:** Image Control → a stock look (Standard, for example). Set **Grain → Off** first, on Negative Film or a
   Cinema look; they share the setting.
2. **Movie mode:** Image Control → a stock look.
3. **U1, U2, U3:** recall each one, set a stock look and Grain Off, then re-save it with *Save USER Settings*.
   A U slot saved with Vivid would otherwise record GR-Log.
4. Power off and on.
5. Flash Ricoh's original `fwdc243b.bin` the same way as above.

## Camera settings for GR-Log video

* Movie mode, dial on **M**, fixed ISO.
* Image Control → **Vivid** (= GR-Log), every slider at **0** (Saturation, Hue, Key, Contrast, highlight/shadow
  contrast, Shading, Clarity). Sharpness to taste; −1 or −2 is common. Grain Off.
* Highlight correction and shadow correction **off**.
* Expose middle grey the way you would for Standard. Highlights clip about 3.5 stops above grey.
* Files are full range (`yuvj420p`, pc). In Resolve, keep Data Levels on Auto/Full and apply `GR-Log-v2_to_Rec709`
  (or a film LUT from `lut-tools/`) after your exposure and white-balance node.
