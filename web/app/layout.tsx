import type { Metadata } from "next";
import "./globals.css";
import Shell from "@/components/Shell";

export const metadata: Metadata = { title: "Kizuna Atlas — analyse du protocole KIZUNA DRIVE", description: "Outil d'analyse des données de l'enquête KIZUNA DRIVE (ICPM Challenge 2026)" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Instrument+Serif&display=swap" />
      </head>
      <body><Shell>{children}</Shell></body>
    </html>
  );
}
