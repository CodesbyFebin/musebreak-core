import "./globals.css";
export const metadata = { title: "MuseBreak — Zero-Trust gateway for Muse", description: "2-gate MetaKey auth" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
