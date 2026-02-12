#!/usr/bin/env node
/**
 * PWA用の正方形PNGアイコンを生成します。
 * 多くのOSはmanifestで正方形アイコンを要求するため、SVGからPNGを生成します。
 */
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import sharp from "sharp";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, "..", "public");
const svgPath = join(publicDir, "pwa-icon.svg");
const svgBuffer = readFileSync(svgPath);

const sizes = [192, 512];

await Promise.all(
  sizes.map(async (size) => {
    const outPath = join(publicDir, `icon-${size}.png`);
    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(outPath);
    console.log(`Generated: icon-${size}.png`);
  })
);

console.log("PWA icon generation complete.");
