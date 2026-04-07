import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SimulateDecision",
  description: "Decision Simulator - AI-Powered Decision Analysis Engine",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
