#!/usr/bin/env node
/**
 * PWA用のスクリーンショットを生成します。
 * - インストールUI用スクリーンショット（デスクトップ/モバイル）
 */
import { mkdirSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import sharp from "sharp";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, "..", "public");
const screenshotsDir = join(publicDir, "screenshots");
const iconPath = join(publicDir, "icon_512x512.png");

// 背景色 #0f172a (background_color)
const bgColor = { r: 15, g: 23, b: 42 };
// スクリーンショット生成（PWAインストールUI用）
if (!existsSync(screenshotsDir)) mkdirSync(screenshotsDir, { recursive: true });

const icon512 = await sharp(iconPath).resize(160, 160).png().toBuffer();

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
