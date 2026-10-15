import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataBuddy",
  description:
    "AI analysis partner for research students — clean, chart, compare, report.",
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
