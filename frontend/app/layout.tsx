import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VTuber Background Loop Generator",
  description: "短い動画クリップを自然にループさせた背景動画を自動生成",
  applicationName: "Loop Video Generator",
  manifest: "/manifest.json",
  themeColor: "#f43f5e",
  // Favicon / PWA アイコン設定
  icons: {
    icon: "/favicon.svg",
    apple: "/favicon.svg",
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
