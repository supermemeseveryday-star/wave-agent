import "./style.css";
export const metadata = { title: "Wave Agent", description: "Agent workspace" };
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  );
}
