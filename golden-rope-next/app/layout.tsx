export const metadata = { title: "Golden Rope — Dashboard" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><div className="container">{children}</div></body>
    </html>
  );
}
