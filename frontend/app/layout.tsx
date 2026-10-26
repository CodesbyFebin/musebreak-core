import "./globals.css";
export const metadata = {
  title: "MuseBreak — Access Control",
  description: "Zero-Trust two-gate authorization for Muse models",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
