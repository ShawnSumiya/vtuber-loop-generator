import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

// --- Favicon SVG Definition (Code-generated icon) ---
// テーマカラー(Indigo-600: #4f46e5)の円形背景に、白い再生マークとループ矢印をあしらったデザイン
// URLエンコードのために '#' を '%23' に置換しています。
const svgFavicon = `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='16' fill='%234f46e5'/><path d='M22 16L12 9V23L22 16Z' fill='white'/><path d='M12 23C8 23 5 20 5 16' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round'/></svg>`;

export const metadata: Metadata = {
  title: "VTuber Background Loop Generator",
  description: "短い動画クリップを自然にループさせた背景動画を自動生成",
  // Favicon 設定
  icons: {
    icon: svgFavicon,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="dark">
      <body className={`${inter.className} antialiased safe-area-padding`}>
        {children}
      </body>
    </html>
  );
}
