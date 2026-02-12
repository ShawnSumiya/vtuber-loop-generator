#!/usr/bin/env node
/**
 * PWA用のアイコンとスクリーンショットを生成します。
 * - 正方形PNGアイコン（192x192, 512x512）
 * - インストールUI用スクリーンショット（デスクトップ/モバイル）
 */
import { readFileSync, mkdirSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import sharp from "sharp";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, "..", "public");
const screenshotsDir = join(publicDir, "screenshots");
const svgPath = join(publicDir, "pwa-icon.svg");
const svgBuffer = readFileSync(svgPath);

// 背景色 #0f172a (background_color)
const bgColor = { r: 15, g: 23, b: 42 };
// アクセント色 #4f46e5 (theme_color)
const accentColor = { r: 79, g: 70, b: 229 };

// 1. アイコン生成
const iconSizes = [192, 512];
await Promise.all(
  iconSizes.map(async (size) => {
    const outPath = join(publicDir, `icon-${size}.png`);
    await sharp(svgBuffer).resize(size, size).png().toFile(outPath);
    console.log(`Generated: icon-${size}.png`);
  })
);

// 2. スクリーンショット生成（PWAインストールUI用）
if (!existsSync(screenshotsDir)) mkdirSync(screenshotsDir, { recursive: true });

const icon512 = await sharp(svgBuffer).resize(160, 160).png().toBuffer();

const createScreenshot = async (width, height, formFactor, filename) => {
  const base = sharp({
    create: { width, height, channels: 3, background: bgColor },
  })
    .png()
    .toBuffer();

  const composed = await sharp(await base)
    .composite([
      {
        input: icon512,
        top: Math.floor((height - 160) / 2),
        left: Math.floor((width - 160) / 2),
      },
    ])
    .png()
    .toFile(join(screenshotsDir, filename));
  console.log(`Generated: screenshots/${filename} (${formFactor})`);
};

await createScreenshot(1280, 720, "wide", "desktop-1280x720.png");
await createScreenshot(390, 844, "narrow", "mobile-390x844.png");

console.log("PWA icon and screenshot generation complete.");
